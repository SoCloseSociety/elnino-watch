#!/usr/bin/env bash
# El Nino Watch: build the dashboard and serve everything on http://127.0.0.1:8911
#
#   ./start.sh            build frontend if needed, (re)start API + collectors
#   ./start.sh stop       stop it (unloads the launchd agent if installed)
#   ./start.sh restart    same as start
#   ./start.sh status     launchd / port / health
#   ./start.sh logs       follow the log (data/elnino.log)
#   ./start.sh install    install the launchd user agent (starts at login, restarts on crash)
#   ./start.sh uninstall  remove the launchd agent (then ./start.sh runs it with nohup)
#
# With the agent installed, start = (re)load it under launchd; stop = `launchctl bootout`
# (a plain kill would just be undone by KeepAlive). Without it, start = nohup uvicorn.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
PORT=8911
LOG=data/elnino.log
LABEL=co.soclose.elninowatch
TEMPLATE="ops/$LABEL.plist"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
UV="$(command -v uv || echo /opt/homebrew/bin/uv)"
# launchd runs the app from a venv OUTSIDE ~/Documents, built on Homebrew Python: macOS TCC
# blocks launchd jobs from ~/Documents unless the binary holds a grant (uv's Python does not,
# Homebrew's does on this Mac). See backend/scripts/serve.py.
AGENT_VENV="$HOME/Library/Application Support/$LABEL/venv"
AGENT_PY_BASE="${ELNINO_AGENT_PYTHON:-/opt/homebrew/bin/python3}"

installed() { [ -f "$AGENT" ]; }
loaded() { launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; }
port_pids() { lsof -ti tcp:$PORT -sTCP:LISTEN 2>/dev/null || true; }

kill_port() {  # stray (non-launchd) server on our port
  local pids; pids="$(port_pids)"
  [ -n "$pids" ] && { echo "$pids" | xargs kill 2>/dev/null || true; sleep 1; }
  return 0
}

wait_health() {
  for _ in $(seq 1 40); do
    curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && {
      echo "El Nino Watch: http://127.0.0.1:$PORT$(installed && echo ' (launchd)')"; return 0; }
    sleep 1
  done
  echo "API did not come up, see $LOG" >&2; return 1
}

build() {
  mkdir -p data
  if [ ! -d frontend/dist ] || [ -n "$(find frontend/src frontend/index.html -newer frontend/dist -print -quit 2>/dev/null)" ]; then
    (cd frontend && { [ -d node_modules ] || npm install --silent; } && npm run build --silent)
  fi
  (cd backend && "$UV" sync -q)
}

build_agent_venv() {
  mkdir -p "$(dirname "$AGENT_VENV")"
  (cd backend && UV_PROJECT_ENVIRONMENT="$AGENT_VENV" "$UV" sync -q --frozen --no-dev \
      --python "$AGENT_PY_BASE")
}

render_agent() {
  mkdir -p "$(dirname "$AGENT")" data
  sed -e "s#__ROOT__#$ROOT#g" -e "s#__PY__#$AGENT_VENV/bin/python#g" -e "s#__HOME__#$HOME#g" \
      -e "s#__PATH__#$(dirname "$UV"):/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin#g" \
      "$TEMPLATE" > "$AGENT"
  plutil -lint "$AGENT" >/dev/null
}

stop() {
  if installed && loaded; then
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    for _ in $(seq 1 10); do loaded || break; sleep 0.5; done
  fi
  kill_port
}

case "${1:-start}" in
  stop)
    stop; echo "stopped"; exit 0 ;;
  logs)
    exec tail -f "$LOG" ;;
  status)
    if installed; then
      if loaded; then echo "launchd: $LABEL loaded ($AGENT)"; else echo "launchd: installed, not loaded"; fi
    else echo "launchd: not installed"; fi
    echo "port $PORT: $(port_pids | tr '\n' ' ')"
    curl -sf "http://127.0.0.1:$PORT/api/health" && echo || echo "health: down"
    exit 0 ;;
  install)
    build; build_agent_venv; stop; render_agent
    launchctl bootstrap "$DOMAIN" "$AGENT"
    echo "installed $AGENT"; wait_health; exit $? ;;
  uninstall)
    stop; rm -f "$AGENT"; echo "uninstalled (run ./start.sh to start without launchd)"; exit 0 ;;
  start|restart|"") ;;
  *) echo "usage: $0 [start|stop|restart|status|logs|install|uninstall]" >&2; exit 2 ;;
esac

build
stop
if installed; then
  build_agent_venv
  render_agent  # picks up template / path changes
  launchctl bootstrap "$DOMAIN" "$AGENT"
else
  (cd backend && nohup "$UV" run --no-sync uvicorn app.main:app --host 127.0.0.1 --port $PORT >> "../$LOG" 2>&1 &)
fi
wait_health
