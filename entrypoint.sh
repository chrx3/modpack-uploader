#!/bin/bash
set -e

# === Setup basic auth ===
mkdir -p /data
if [ -n "$HTPASSWD_HASH" ]; then
    echo "chris:$HTPASSWD_HASH" > /data/.htpasswd
    echo "[entrypoint] htpasswd installed from env"
elif [ -f /data/.htpasswd ]; then
    echo "[entrypoint] using existing htpasswd"
elif [ -n "$UPLOAD_USER" ] && [ -n "$UPLOAD_PASS" ]; then
    HASH=$(htpasswd -nbm "$UPLOAD_USER" "$UPLOAD_PASS")
    echo "$HASH" > /data/.htpasswd
    echo "[entrypoint] htpasswd generated for user $UPLOAD_USER"
else
    echo "[entrypoint] ERROR: no HTPASSWD_HASH, no UPLOAD_PASS, no .htpasswd"
    exit 1
fi

# === Start Python uploader backend ===
echo "[entrypoint] starting uploader backend on :5050"
python3 /usr/local/bin/uploader_backend.py &

# === Wait briefly then start nginx in foreground ===
sleep 1
echo "[entrypoint] starting nginx"
exec nginx -g "daemon off;"
