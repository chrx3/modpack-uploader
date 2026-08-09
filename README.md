# Modpack Uploader

Serves a static landing page + protected upload endpoint + public downloads
for ChrisCraft Minecraft modpacks, plus a small panel to switch which
Minecraft server is running.

## Layout
- `Dockerfile` — nginx:alpine + Flask + htpasswd
- `nginx.conf` — routing (Basic Auth on /upload and /panel, public /files)
- `uploader_backend.py` — POST /api/upload (validates mrpack zip) + panel API
- `html/index.html` — landing with list of available packs
- `html/upload.html` — drag-drop form with auth
- `html/panel.html` — server switch panel

## Env vars (set in Coolify)
- `UPLOAD_USER` — basic auth user (default: chris)
- `UPLOAD_PASS` — basic auth password. Changing it and redeploying now
  rotates the credential; the old entrypoint only wrote `.htpasswd` when the
  file was missing, so every change after the first one was silently ignored.
- `PANEL_TOKEN` — optional. If unset, a random token is generated once and
  stored at `/data/.panel-token`.

## Data volumes
- `/data/incoming` — newly uploaded .mrpack (cron picks up)
- `/data/files`    — public download area
- `/data/logs`     — Flask + nginx logs
- `/data/.htpasswd` — generated from UPLOAD_USER/UPLOAD_PASS at startup
- `/data/.panel-token` — token for the panel API
- `/data/.mcswitch.sock` — Unix socket published by the host agent (read-only
  from this container's point of view; it just connects)

## Server switch panel

`/panel/` lists the available servers and lets you activate one. Only one runs
at a time, always on port 25565, so the address never changes.

The container has no access to the Docker socket. It forwards a closed set of
operations — `use`, `main`, `stop` — to `mcswitch-agent`, a root service on the
host, over a Unix socket shared through the `/data` bind mount. The agent
validates the operation against a fixed list and the profile name against a
strict regex; nothing that arrives from the browser is ever passed to a shell.

Two independent secrets are needed: Basic Auth to load `/panel/`, and
`X-Panel-Token` for every call to `/api/panel/*`.

Creating and deleting profiles stays on the host, via `mcswitch new` and
`mcswitch rm` — a delete wipes that profile's world, which is not something
that belongs behind a button on a public page.

### Host side (not in this repo)
- `/usr/local/bin/mcswitch` — the CLI
- `/root/mc-lab/mcswitch-agent.py` + `mcswitch-agent.service`
- `/root/mc-lab/profiles/<name>/` — one `profile.env` and one `data/` per server
