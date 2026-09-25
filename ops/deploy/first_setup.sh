#!/usr/bin/env bash
# One-time (idempotent) setup of El Nino Watch ON the VPS (Ubuntu/Debian). Run as root, after
# deploy.sh has pushed the code to /opt/elnino/app:
#
#   ssh <your-vps> 'DOMAIN=elnino.example.com bash /opt/elnino/app/ops/deploy/first_setup.sh'
#
# (or `DOMAIN=... bash ops/deploy/deploy.sh --setup` from your workstation, which does both).
#
# Layout (everything under /opt/elnino; nothing else on the box is touched except the
# files named below):
#   /opt/elnino/app      code (root-owned, read-only for the service; deploy.sh rsyncs it)
#   /opt/elnino/data     SQLite DB (owned by the `elnino` system user; never rsynced)
#   /opt/elnino/.env     settings + ADMIN_TOKEN (root:elnino 640; never rsynced)
#   /opt/elnino/venv     Python venv (uv sync --frozen), /opt/elnino/python = uv's Python
#   /etc/systemd/system/elnino-watch.service, /etc/logrotate.d/elnino-watch,
#   /etc/nginx/sites-{available,enabled}/elnino, /var/log/elnino-watch.log
#
# Env knobs: PORT (default 8911, only used when .env is created), DOMAIN (default
# elnino.example.com), EXTRA_DOMAINS (e.g. "www.elnino.example.com"),
# FORCE_NGINX=1 (re-render the nginx site, backup first), SKIP_CERTBOT=1,
# CERTBOT_EMAIL (only needed if certbot has no account on this box yet).
set -euo pipefail

BASE=/opt/elnino
APP=$BASE/app
DATA=$BASE/data
ENV_FILE=$BASE/.env
VENV=$BASE/venv
PYDIR=$BASE/python
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE=elnino-watch
SITE=/etc/nginx/sites-available/elnino
DOMAIN="${DOMAIN:-elnino.example.com}"
EXTRA_DOMAINS="${EXTRA_DOMAINS:-}"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root"
[ "$(uname -s)" = Linux ] || die "this script runs on the VPS (Linux), not here"
[ -f "$APP/backend/pyproject.toml" ] || die "no code in $APP yet: run deploy.sh first"
[ -f "$APP/frontend/dist/index.html" ] || die "no built frontend in $APP/frontend/dist"

log "Preflight"
free -m | sed -n '1,2p'
PORT_IN_ENV=$(sed -n 's/^PORT=\([0-9]*\).*/\1/p' "$ENV_FILE" 2>/dev/null | tail -1 || true)
PORT="${PORT_IN_ENV:-${PORT:-8911}}"
if [ -n "$(ss -ltnH "sport = :$PORT")" ] && ! systemctl is-active --quiet "$SERVICE"; then
    ss -ltnp "sport = :$PORT" || true
    die "port $PORT is already used by something else: set PORT=... and rerun"
fi
echo "port $PORT: ok"

log "System user + directories"
if ! id elnino >/dev/null 2>&1; then
    useradd --system --home-dir "$BASE" --no-create-home --shell /usr/sbin/nologin elnino
fi
install -d -o root -g root -m 755 "$BASE" "$APP"
install -d -o elnino -g elnino -m 750 "$DATA"
chown -R elnino:elnino "$DATA"   # a DB seeded by deploy.sh --seed-db arrives root-owned
touch /var/log/elnino-watch.log && chmod 640 /var/log/elnino-watch.log

log "uv"
if ! command -v uv >/dev/null 2>&1; then
    command -v curl >/dev/null || apt-get install -y curl
    curl -LsSf https://astral.sh/uv/install.sh \
        | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh
fi
uv --version

log ".env"
if [ ! -f "$ENV_FILE" ]; then
    token="$(openssl rand -hex 32)"
    sed -e "s/^ADMIN_TOKEN=.*/ADMIN_TOKEN=$token/" -e "s/^PORT=.*/PORT=$PORT/" \
        "$HERE/env.example" > "$ENV_FILE"
    unset token
    echo "created $ENV_FILE with a fresh ADMIN_TOKEN (read it with: grep ADMIN_TOKEN $ENV_FILE)"
else
    echo "kept existing $ENV_FILE"
fi
grep -q '^ADMIN_TOKEN=[0-9a-f]\{64\}$' "$ENV_FILE" \
    || echo "WARNING: ADMIN_TOKEN in $ENV_FILE is not 64 hex chars (openssl rand -hex 32)"
chown root:elnino "$ENV_FILE"
chmod 640 "$ENV_FILE"

log "Python deps (uv sync --frozen --no-dev -> $VENV)"
install -d -o root -g root -m 755 "$PYDIR"
(
    cd "$APP/backend"
    UV_PROJECT_ENVIRONMENT="$VENV" UV_PYTHON_INSTALL_DIR="$PYDIR" \
    UV_PYTHON_PREFERENCE=only-managed UV_CACHE_DIR=/var/cache/elnino-uv \
        uv sync --frozen --no-dev --python 3.12 --compile-bytecode
)
chmod -R go+rX "$VENV" "$PYDIR"

log "systemd unit"
install -m 644 "$HERE/elnino-watch.service" /etc/systemd/system/$SERVICE.service
systemctl daemon-reload
systemctl enable $SERVICE >/dev/null

log "logrotate"
install -m 644 "$HERE/logrotate-elnino-watch" /etc/logrotate.d/elnino-watch
logrotate -d /etc/logrotate.d/elnino-watch >/dev/null 2>&1 || echo "WARNING: logrotate -d complained"

log "Start the service"
systemctl restart $SERVICE
ok=""
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then ok=1; break; fi
    sleep 1
done
[ -n "$ok" ] || { journalctl -u $SERVICE -n 30 --no-pager; tail -n 30 /var/log/elnino-watch.log; die "health check failed"; }
curl -fsS "http://127.0.0.1:$PORT/api/health"; echo
curl -fsS "http://127.0.0.1:$PORT/api/access"; echo

log "nginx site"
command -v nginx >/dev/null || die "nginx is not installed"
names="$DOMAIN${EXTRA_DOMAINS:+ $EXTRA_DOMAINS}"
if [ ! -f "$SITE" ] || [ "${FORCE_NGINX:-0}" = 1 ]; then
    [ -f "$SITE" ] && cp -a "$SITE" "$SITE.bak.$(date +%Y%m%d%H%M%S)"
    sed -e "s/__PORT__/$PORT/g" -e "s/__SERVER_NAMES__/$names/g" \
        "$HERE/nginx-elnino.conf" > "$SITE"
    echo "wrote $SITE (server_name $names)"
else
    echo "kept existing $SITE (FORCE_NGINX=1 to re-render; certbot edits would be lost)"
fi
ln -sf "$SITE" /etc/nginx/sites-enabled/elnino
if ! nginx -t; then
    rm -f /etc/nginx/sites-enabled/elnino
    die "nginx -t failed: site disabled again, other sites untouched"
fi
systemctl reload nginx
curl -fsS -o /dev/null -w "http://$DOMAIN/api/health via nginx: %{http_code}\n" \
    -H "Host: $DOMAIN" "http://127.0.0.1/api/health" || true

log "TLS (certbot --nginx)"
if [ "${SKIP_CERTBOT:-0}" = 1 ]; then
    echo "skipped (SKIP_CERTBOT=1)"
else
    if ! command -v certbot >/dev/null; then
        apt-get update -q && apt-get install -y certbot python3-certbot-nginx
    fi
    args=(--nginx --non-interactive --agree-tos --redirect --keep-until-expiring -d "$DOMAIN")
    for d in $EXTRA_DOMAINS; do args+=(-d "$d"); done
    if [ -n "${CERTBOT_EMAIL:-}" ]; then args+=(-m "$CERTBOT_EMAIL"); fi
    if certbot "${args[@]}"; then
        nginx -t && systemctl reload nginx
    else
        echo "WARNING: certbot failed; the site still answers on http://$DOMAIN"
    fi
fi

log "Done"
echo "URL:     https://$DOMAIN"
echo "Service: systemctl status $SERVICE   Logs: tail -f /var/log/elnino-watch.log"
