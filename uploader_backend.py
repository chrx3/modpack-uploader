#!/usr/bin/env python3
"""Modpack upload backend.

POST /api/upload   — receives .mrpack file, saves to /data/incoming/<name>.mrpack
GET  /upload/      — handled by nginx static (upload.html)
"""
import os
import re
import sys
import json
import shutil
import hashlib
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, abort

INCOMING = Path("/data/incoming")
FILES = Path("/data/files")
LOGS = Path("/data/logs")
PROCESSED = Path("/data/processed")

for d in (INCOMING, FILES, LOGS, PROCESSED):
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOGS / "upload.log"), logging.StreamHandler()],
)
log = logging.getLogger("uploader")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

# Mark file as "seen" so the processor cron doesn't double-process
PROCESSED_MARKER = Path("/data/.processed.json")


def load_processed() -> dict:
    if PROCESSED_MARKER.exists():
        try:
            return json.loads(PROCESSED_MARKER.read_text())
        except Exception:
            pass
    return {"files": {}}


def save_processed(d: dict) -> None:
    PROCESSED_MARKER.write_text(json.dumps(d, indent=2))


def safe_filename(name: str) -> str:
    """Strip path components + enforce .mrpack extension."""
    name = os.path.basename(name)
    name = re.sub(r"[^A-Za-z0-9._\-]", "_", name)
    if not name.endswith(".mrpack"):
        # If user uploaded .zip or other, force .mrpack
        name = re.sub(r"\.[A-Za-z0-9]+$", "", name) + ".mrpack"
    return name


def detect_format(path: Path) -> dict:
    """Quick sanity check on the uploaded file."""
    try:
        with open(path, "rb") as f:
            head = f.read(4)
    except Exception as e:
        return {"ok": False, "error": f"unreadable: {e}"}

    # ZIP magic = PK\x03\x04 (mrpack is a zip)
    if head[:2] == b"PK":
        # Try to find manifest.json inside the zip
        import zipfile
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                has_manifest = "modrinth.index.json" in names
                mc_version = None
                loader = None
                if has_manifest:
                    import json as j
                    m = j.loads(zf.read("modrinth.index.json"))
                    mc_version = m.get("dependencies", {}).get("minecraft")
                    loader_key = m.get("dependencies", {}).get("fabric-loader") \
                                 or m.get("dependencies", {}).get("forge") \
                                 or m.get("dependencies", {}).get("quilt-loader")
                    loader = loader_key
                return {
                    "ok": True,
                    "format": "mrpack (zip)",
                    "size": path.stat().st_size,
                    "files_in_zip": len(names),
                    "has_manifest": has_manifest,
                    "mc_version": mc_version,
                    "loader": loader,
                }
        except zipfile.BadZipFile:
            return {"ok": False, "error": "not a valid zip"}
    elif head[:4] == b"\x50\x4b\x05\x06":
        return {"ok": False, "error": "empty zip archive"}
    else:
        return {"ok": False, "error": f"unknown format, magic={head[:4].hex()}"}


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no file part"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "empty filename"}), 400

    name = safe_filename(f.filename)
    dest = INCOMING / name

    # Save atomically: write to .tmp then rename
    tmp = dest.with_suffix(dest.suffix + ".part")
    f.save(tmp)

    sha = hashlib.sha256()
    with open(tmp, "rb") as r:
        for chunk in iter(lambda: r.read(65536), b""):
            sha.update(chunk)
    digest = sha.hexdigest()

    info = detect_format(tmp)
    if not info["ok"]:
        tmp.unlink(missing_ok=True)
        return jsonify({"ok": False, "error": info["error"]}), 400

    tmp.rename(dest)
    stat = dest.stat()

    # Also copy to public files/ for immediate download (processor will rewrite metadata)
    public_dest = FILES / name
    shutil.copy2(dest, public_dest)

    # Mark as seen (processor will pick up)
    seen = load_processed()
    seen["files"][name] = {
        "received_at": datetime.utcnow().isoformat() + "Z",
        "size": stat.st_size,
        "sha256": digest,
        "info": info,
        "status": "pending",
    }
    save_processed(seen)

    log.info(f"RECEIVED {name} ({stat.st_size} bytes, sha={digest[:12]})")

    return jsonify({
        "ok": True,
        "filename": name,
        "size": stat.st_size,
        "sha256": digest,
        "format": info,
        "download_url": f"/files/{name}",
        "message": "received, queued for processing",
    })


@app.route("/api/status")
def status():
    seen = load_processed()
    incoming = sorted(p.name for p in INCOMING.glob("*.mrpack"))
    files = sorted(p.name for p in FILES.glob("*.mrpack"))
    return jsonify({
        "ok": True,
        "incoming": incoming,
        "files_ready": files,
        "processed": seen.get("files", {}),
    })


@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    # Listen on localhost only (nginx in front)
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
