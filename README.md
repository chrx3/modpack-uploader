# Modpack Uploader

Serves a static landing page + protected upload endpoint + public downloads
for ChrisCraft Minecraft modpacks.

## Layout
- `Dockerfile` — nginx:alpine + Flask + htpasswd
- `nginx.conf` — routing (Basic Auth on /upload, public /files)
- `uploader_backend.py` — POST /api/upload (validates mrpack zip)
- `html/index.html` — landing with list of available packs
- `html/upload.html` — drag-drop form with auth

## Env vars (set in Coolify)
- `UPLOAD_USER` — basic auth user (default: chris)
- `UPLOAD_PASS` — basic auth password

## Data volumes
- `/data/incoming` — newly uploaded .mrpack (cron picks up)
- `/data/files`    — public download area
- `/data/logs`     — Flask + nginx logs
- `/data/.htpasswd` — generated from UPLOAD_USER/UPLOAD_PASS at startup
