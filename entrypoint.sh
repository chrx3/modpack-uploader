#!/bin/bash
set -e

# === Setup basic auth ===
# UPLOAD_USER/UPLOAD_PASS win over any existing file, so changing the password
# in Coolify and redeploying actually rotates it. Before, an existing
# .htpasswd on the volume made every later change a no-op.
mkdir -p /data
if [ -n "$HTPASSWD_HASH" ]; then
    echo "chris:$HTPASSWD_HASH" > /data/.htpasswd
    echo "[entrypoint] htpasswd installed from env"
elif [ -n "$UPLOAD_USER" ] && [ -n "$UPLOAD_PASS" ]; then
    # -nbs = SHA-1 format (matches what the Python uploader_backend.py expects)
    HASH=$(htpasswd -nbs "$UPLOAD_USER" "$UPLOAD_PASS")
    echo "$HASH" > /data/.htpasswd
    echo "[entrypoint] htpasswd (re)generated for user $UPLOAD_USER (SHA format)"
elif [ -f /data/.htpasswd ]; then
    echo "[entrypoint] using existing htpasswd"
else
    echo "[entrypoint] ERROR: no HTPASSWD_HASH, no UPLOAD_PASS, no .htpasswd"
    exit 1
fi

# === Token del panel de servidores ===
# Independiente del de subida: el panel puede apagar y prender servidores.
# Se genera una sola vez y queda en el volumen.
if [ -n "$PANEL_TOKEN" ]; then
    printf '%s' "$PANEL_TOKEN" > /data/.panel-token
    echo "[entrypoint] panel token tomado de la variable de entorno"
elif [ ! -s /data/.panel-token ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > /data/.panel-token
    echo "[entrypoint] panel token generado (mira /data/.panel-token en el host)"
else
    echo "[entrypoint] panel token ya existente"
fi
chmod 600 /data/.panel-token

if [ -S /data/.mcswitch.sock ]; then
    echo "[entrypoint] agente mcswitch detectado"
else
    echo "[entrypoint] aviso: no hay socket mcswitch; el panel mostrara el server como no disponible"
fi

# === Start Python uploader backend ===
echo "[entrypoint] starting uploader backend on :5050"
python3 /usr/local/bin/uploader_backend.py &

# === Wait briefly then start nginx in foreground ===
sleep 1
echo "[entrypoint] starting nginx"
exec nginx -g "daemon off;"
