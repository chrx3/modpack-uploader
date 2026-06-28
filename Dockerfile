FROM nginx:alpine

# Tools for upload handling + auth
RUN apk add --no-cache \
    python3 py3-pip py3-yaml \
    apache2-utils \
    bash \
    && pip3 install --break-system-packages --quiet flask requests

# Nginx main config (paths to be replaced at runtime)
COPY nginx.conf /etc/nginx/nginx.conf

# Static landing + upload scripts
COPY html/ /var/www/html/
COPY uploader_backend.py /usr/local/bin/uploader_backend.py
RUN chmod +x /usr/local/bin/uploader_backend.py

# Data dirs (mounted as volume)
RUN mkdir -p /data/incoming /data/files /data/processed /data/logs

# Entrypoint: setup htpasswd from env, validate, run nginx
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s CMD wget -q -O /dev/null http://localhost/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
