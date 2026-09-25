#!/usr/bin/env bash
# shellcheck disable=SC2029  # remote ssh commands expand local vars on purpose
# Deploy El Nino Watch from your workstation to a Linux VPS over ssh (alias/host in ELNINO_HOST).
#
#   bash ops/deploy/deploy.sh --dry-run   # build + tests, then show what rsync WOULD change
#   bash ops/deploy/deploy.sh --setup     # first time: push code, then run first_setup.sh
#   bash ops/deploy/deploy.sh             # every later release
#
# What it does: backend tests + ruff, `npm run build`, rsync backend/ + frontend/dist/ +
# ops/deploy/ into /opt/elnino/app/ (--delete stays INSIDE those three target dirs;
# /opt/elnino/data, /opt/elnino/.env and the venv are never touched), remote
# `uv sync --frozen --no-dev`, `systemctl restart elnino-watch`, health check.
#
# Options: --dry-run, --setup, --seed-db (copy a snapshot of the local data/elnino.db
# to the VPS, only if the VPS has no DB yet), --skip-tests, --skip-build,
# --host <ssh alias> (default $ELNINO_HOST or `elnino-vps`). Env: DOMAIN (the public host name).
set -euo pipefail

HOST="${ELNINO_HOST:-elnino-vps}"
DRY=0; SETUP=0; SEED=0; TESTS=1; BUILD=1
DOMAIN="${DOMAIN:-elnino.example.com}"
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY=1 ;;
        --setup) SETUP=1 ;;
        --seed-db) SEED=1 ;;
        --skip-tests) TESTS=0 ;;
        --skip-build) BUILD=0 ;;
        --host) HOST="$2"; shift ;;
        -h|--help) sed -n '3,17p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REMOTE=/opt/elnino/app
UV_ENV="UV_PROJECT_ENVIRONMENT=/opt/elnino/venv UV_PYTHON_INSTALL_DIR=/opt/elnino/python \
UV_PYTHON_PREFERENCE=only-managed UV_CACHE_DIR=/var/cache/elnino-uv"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# rsync >= 3.1 for --chown (macOS /usr/bin/rsync is 2.6.9 or openrsync)
RSYNC=rsync
[ -x /opt/homebrew/bin/rsync ] && RSYNC=/opt/homebrew/bin/rsync
"$RSYNC" --version 2>/dev/null | sed -n 1p | grep -Eq 'version (3\.[1-9]|[4-9])' \
    || die "need rsync >= 3.1 (brew install rsync)"

log "Checks (local)"
cd "$ROOT"
if grep -rIl $'\xe2\x80\x94' backend/app frontend/src ops/deploy DEPLOY.md 2>/dev/null; then
    echo "WARNING: em dash in the files above (project rule: use --)"
fi
if [ "$TESTS" = 1 ]; then
    (cd backend && uv run pytest -q && uv run ruff check app)
fi

if [ "$BUILD" = 1 ]; then
    log "Build frontend"
    (cd frontend && npm run build)
fi
[ -f frontend/dist/index.html ] || die "frontend/dist missing (build failed?)"

RS=("$RSYNC" -rlptz --delete --chown=root:root "--chmod=Dgo+rx,Fgo+r,go-w"
    --exclude=.venv/ --exclude=__pycache__/ --exclude=.pytest_cache/ --exclude=.ruff_cache/
    --exclude=/data/ --exclude=.env --exclude='*.db*' --exclude=.DS_Store)
[ "$DRY" = 1 ] && RS+=(--dry-run --itemize-changes)

log "Target $HOST:$REMOTE"
if ! ssh "$HOST" "test -d $REMOTE"; then
    echo "$REMOTE does not exist yet (first deploy)"
    if [ "$DRY" = 1 ]; then
        echo "dry-run: would create $REMOTE/{backend,frontend/dist,ops/deploy} and push everything"
        exit 0
    fi
    [ "$SETUP" = 1 ] || die "first deploy: rerun with --setup"
fi
# Idempotent: $REMOTE may pre-exist without its subdirs (rsync won't create nested parents).
[ "$DRY" = 1 ] || ssh "$HOST" "install -d -m 755 /opt/elnino $REMOTE $REMOTE/frontend $REMOTE/ops"

log "rsync (--delete only inside $REMOTE/{backend,frontend/dist,ops/deploy})"
"${RS[@]}" backend/ "$HOST:$REMOTE/backend/"
"${RS[@]}" frontend/dist/ "$HOST:$REMOTE/frontend/dist/"
"${RS[@]}" ops/deploy/ "$HOST:$REMOTE/ops/deploy/"

if [ "$DRY" = 1 ]; then
    log "dry-run: nothing changed. Would then run on $HOST:"
    echo "  cd $REMOTE/backend && $UV_ENV uv sync --frozen --no-dev --python 3.12 --compile-bytecode"
    echo "  systemctl restart elnino-watch && curl http://127.0.0.1:<PORT>/api/health"
    exit 0
fi

if [ "$SEED" = 1 ]; then
    log "Seed DB (only if the VPS has none)"
    if ssh "$HOST" "test -e /opt/elnino/data/elnino.db"; then
        echo "VPS already has /opt/elnino/data/elnino.db: not overwritten"
    else
        snap="$(mktemp -d)/elnino.db"
        sqlite3 data/elnino.db ".backup '$snap'"
        # the household checklist stays on the workstation
        sqlite3 "$snap" "DELETE FROM status WHERE key='prep_state';"
        ssh "$HOST" "systemctl stop elnino-watch 2>/dev/null || true; install -d /opt/elnino/data"
        "$RSYNC" -z "$snap" "$HOST:/opt/elnino/data/elnino.db"
        ssh "$HOST" "id elnino >/dev/null 2>&1 && chown elnino:elnino /opt/elnino/data/elnino.db; chmod 640 /opt/elnino/data/elnino.db"
        rm -f "$snap"
    fi
fi

if [ "$SETUP" = 1 ]; then
    log "first_setup.sh on $HOST"
    ssh -t "$HOST" "bash $REMOTE/ops/deploy/first_setup.sh"
else
    log "uv sync + restart on $HOST"
    ssh "$HOST" "set -e; cd $REMOTE/backend && $UV_ENV uv sync --frozen --no-dev --python 3.12 --compile-bytecode \
        && chmod -R go+rX /opt/elnino/venv && systemctl restart elnino-watch"
fi

log "Health check"
PORT=$(ssh "$HOST" "sed -n 's/^PORT=\([0-9]*\).*/\1/p' /opt/elnino/.env | tail -1")
ok=""
for _ in $(seq 1 30); do
    if ssh "$HOST" "curl -fsS http://127.0.0.1:${PORT:-8911}/api/health" 2>/dev/null; then ok=1; break; fi
    sleep 2
done
echo
[ -n "$ok" ] || { ssh "$HOST" "systemctl status elnino-watch --no-pager | head -20; tail -n 40 /var/log/elnino-watch.log"; die "service not healthy"; }
code=$(curl -s -o /dev/null -w '%{http_code}' "https://$DOMAIN/api/health" || true)
echo "public https://$DOMAIN/api/health -> $code"

log "Deployed: https://$DOMAIN"
