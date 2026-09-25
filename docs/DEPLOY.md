# Deploying El Nino Watch on a Linux VPS

A public, SEO-indexed deployment on a small Linux VPS (tested on Ubuntu 20.04+, 2 vCPU,
under 1 GB of RAM for this service; it coexists with other nginx sites on the same box).
The kit lives in `ops/deploy/`. Replace `elnino.example.com` with your host name and
`<your-vps>` with your ssh alias (`ELNINO_HOST`) throughout.

Nothing here runs automatically: every VPS step is a command you run.

## Topology

```
browser --https--> nginx (site "elnino")
                    |-- /assets/*, /favicon.svg               static, from /opt/elnino/app/frontend/dist
                    |-- /robots.txt, /sitemap.xml             --> app (generated from live data)
                    |-- /api/*        --> 127.0.0.1:8911      (limit 10 r/s, burst 40)
                    |-- /api/webcams/<id>/snapshot            (limit 2 r/s, burst 10)
                    `-- /, SPA routes, /index.html --> app    (adds CSP + no-cache)
systemd elnino-watch.service: uvicorn, 1 worker (the collector scheduler is in-process),
User=elnino, MemoryMax=550M, Restart=always, logs /var/log/elnino-watch.log
```

| Path on the VPS | What | Touched by deploy.sh |
|---|---|---|
| `/opt/elnino/app/{backend,frontend/dist,ops/deploy}` | code (root-owned, read-only for the service) | yes, `rsync --delete` inside these 3 dirs only |
| `/opt/elnino/data/elnino.db` | SQLite DB (owned by `elnino`) | never (except `--seed-db` when it does not exist) |
| `/opt/elnino/.env` | settings + `ADMIN_TOKEN` (root:elnino 640) | never |
| `/opt/elnino/venv`, `/opt/elnino/python` | venv from `uv sync --frozen`, uv-managed Python 3.12 | rebuilt by `uv sync` |
| `/etc/systemd/system/elnino-watch.service`, `/etc/logrotate.d/elnino-watch`, `/etc/nginx/sites-available/elnino` | service, log rotation, nginx site | first_setup.sh only |

Port **8911** by default (`PORT` in `.env`); `first_setup.sh` refuses to continue if the
port is taken. RAM: the unit caps the service at 550 MB (`MemoryHigh` 450 MB); the app is
designed to stay well under that (bounded caches, downsampled hourly data, streaming
parsers for the big upstream files).

## What public mode changes (`PUBLIC_MODE=true`, `backend/app/security.py`)

- Every non-GET/HEAD/OPTIONS `/api` request needs `X-Admin-Token: <ADMIN_TOKEN>` (else
  403): verify/run sources, refresh the briefing, re-evaluate the local risk, save the
  preparedness state, edit the shared places. `GET /api/layers/verify` is admin-only too
  (it hits every tile server).
- `GET /api/preparedness/state` answers 404 to visitors: each browser keeps its own
  checklist in localStorage and nobody sees the operator's household numbers (the same
  document is also stripped from `/api/status`).
- `GET /api/briefing` builds on demand only if none exists (one build at a time);
  `GET /api/layers` is served from a 60 s shared cache; places search / preview have
  bounded caches and an hourly upstream budget.
- `/docs`, `/redoc`, `/openapi.json` are off. Security headers + a strict CSP on every
  response; HSTS once served over https.
- `GET /api/access` -> `{public_mode, admin}` (the frontend hides admin buttons).

Admin call example:

```bash
TOKEN=$(ssh <your-vps> "sed -n 's/^ADMIN_TOKEN=//p' /opt/elnino/.env")
curl -X POST -H "X-Admin-Token: $TOKEN" https://elnino.example.com/api/briefing/refresh
```

## First deployment

Prerequisites on your workstation: `uv`, Node 22+, rsync >= 3.1 (`brew install rsync` on
macOS), an ssh alias to the VPS with root access. On the VPS: nginx installed, DNS for
`elnino.example.com` pointing at it (an A record; `ops/deploy/ionos_dns.sh` is a helper for
IONOS-hosted zones, adapt or ignore it for other registrars).

1. Local checks + preview of what would be pushed (read-only on the VPS):
   ```bash
   ELNINO_HOST=<your-vps> DOMAIN=elnino.example.com bash ops/deploy/deploy.sh --dry-run
   ```
2. Push the code and run the one-time setup (user `elnino`, dirs, uv, `.env` with a
   fresh ADMIN_TOKEN, `uv sync`, systemd unit, logrotate, nginx site + `nginx -t` +
   reload, certbot `--nginx` for the domain). `--seed-db` copies a snapshot of your local DB
   (minus the preparedness state) so the site is not empty for the first hours; drop it to
   start from an empty DB:
   ```bash
   ELNINO_HOST=<your-vps> DOMAIN=elnino.example.com bash ops/deploy/deploy.sh --setup --seed-db
   ```
   The same setup, step by step, if preferred:
   ```bash
   bash ops/deploy/deploy.sh --setup --skip-tests --skip-build   # only after step 1 built and tested
   # or, with the code already on the VPS:
   ssh <your-vps> 'DOMAIN=elnino.example.com bash /opt/elnino/app/ops/deploy/first_setup.sh'
   ```
   `first_setup.sh` knobs: `PORT`, `DOMAIN`, `EXTRA_DOMAINS`, `FORCE_NGINX=1`,
   `SKIP_CERTBOT=1`, `CERTBOT_EMAIL`.
3. Settings and optional credentials (see `ops/deploy/env.example`; at least
   `PUBLIC_ORIGIN`, and `HOME_*` if you watch another point):
   ```bash
   ssh -t <your-vps> 'nano /opt/elnino/.env && systemctl restart elnino-watch'
   ```
   Keep `TELEGRAM_*` / `NEO_API_*` empty on the VPS while a local instance also sends
   alerts, otherwise every alert arrives twice.
4. Check:
   ```bash
   curl -s https://elnino.example.com/api/health
   curl -s https://elnino.example.com/api/access           # public_mode: true
   curl -s -o /dev/null -w '%{http_code}\n' -X POST https://elnino.example.com/api/sources/verify   # 403
   ```

If certbot fails (Let's Encrypt rate limits, DNS not propagated yet), the site still answers
on http; retry later with `ssh <your-vps> 'certbot --nginx --redirect -d elnino.example.com'`.

## Later releases

```bash
bash ops/deploy/deploy.sh            # tests + ruff, npm run build, rsync, uv sync, restart, health check
bash ops/deploy/deploy.sh --dry-run  # see what would change first
```

deploy.sh never touches `/opt/elnino/data` or `/opt/elnino/.env`. The nginx site and the
systemd unit are only (re)installed by first_setup.sh: after changing
`ops/deploy/elnino-watch.service`, run
`ssh <your-vps> 'install -m 644 /opt/elnino/app/ops/deploy/elnino-watch.service /etc/systemd/system/ && systemctl daemon-reload && systemctl restart elnino-watch'`.
After changing `ops/deploy/nginx-elnino.conf`, re-render with
`ssh <your-vps> 'FORCE_NGINX=1 DOMAIN=elnino.example.com bash /opt/elnino/app/ops/deploy/first_setup.sh'`
(backs up the old site; certbot then re-adds its 443 block).

## Frontend home point

The backend follows `HOME_NAME` / `HOME_LAT` / `HOME_LON` / `HOME_RADIUS_KM` from `.env`.
The frontend bundle carries its own copy for the map circle and the distance filters; set
the same values in `frontend/.env.local` (ignored by git) before `npm run build` /
`deploy.sh`:

```
VITE_HOME_NAME=Koh Samui
VITE_HOME_LAT=9.512
VITE_HOME_LON=100.013
VITE_HOME_RADIUS_KM=800
```

## Adding a second host name

1. DNS: an A record for the new name pointing at the VPS.
2. Add it to the nginx site and expand the certificate:
   ```bash
   ssh <your-vps> "sed -i 's/server_name elnino.example.com;/server_name elnino.example.com www.elnino.example.com;/' /etc/nginx/sites-available/elnino && nginx -t && systemctl reload nginx"
   ssh <your-vps> 'certbot --nginx --expand --redirect -d elnino.example.com -d www.elnino.example.com'
   ```
   (certbot may have split the site into a port-80 and a port-443 server block: the sed
   updates every `server_name` line that lists only the first name; check with
   `grep -n server_name /etc/nginx/sites-available/elnino`.)
3. For SEO keep one canonical host: `PUBLIC_ORIGIN` in `.env`, and a 301 from the other
   name (see `backend/docs/SEO.md`, "Moving to a new domain").

## Rotate the admin token

```bash
ssh <your-vps> 'sed -i "s/^ADMIN_TOKEN=.*/ADMIN_TOKEN=$(openssl rand -hex 32)/" /opt/elnino/.env && systemctl restart elnino-watch'
```

The old token stops working at the restart. Update any script or bot that uses it.

## Logs and status

```bash
ssh <your-vps> 'systemctl status elnino-watch --no-pager'
ssh <your-vps> 'tail -f /var/log/elnino-watch.log'          # app + collectors (rotated daily, 14 kept)
ssh <your-vps> 'tail -f /var/log/nginx/elnino.access.log'   # 429 = rate limit hit
ssh <your-vps> 'systemctl show elnino-watch -p MemoryCurrent'
curl -s https://elnino.example.com/api/sources | jq '[.[] | select(.state != "ok") | {name, state}]'
```

## Rollback

Code only (the DB and .env are not versioned by deploy.sh):

```bash
git checkout <previous-good-commit>      # or git stash the bad change
bash ops/deploy/deploy.sh                # pushes that version, uv sync, restart
git checkout -                           # back to your branch
```

Emergency stop, site offline (other sites on the box keep running):

```bash
ssh <your-vps> 'systemctl stop elnino-watch && rm -f /etc/nginx/sites-enabled/elnino && nginx -t && systemctl reload nginx'
```

Bring it back: `ssh <your-vps> 'ln -s /etc/nginx/sites-available/elnino /etc/nginx/sites-enabled/elnino && nginx -t && systemctl reload nginx && systemctl start elnino-watch'`.

DB backup before a risky change (`apt-get install -y sqlite3` if the CLI is missing):
`ssh <your-vps> "sqlite3 /opt/elnino/data/elnino.db \".backup /opt/elnino/data/elnino-$(date +%F).db\""`.

Full removal: stop + disable the service, remove the nginx site (as above),
`certbot delete --cert-name elnino.example.com`, then
`rm -rf /opt/elnino /etc/systemd/system/elnino-watch.service /etc/logrotate.d/elnino-watch && userdel elnino`.

## Local install on macOS (no VPS)

`./start.sh install` renders `ops/co.soclose.elninowatch.plist` into
`~/Library/LaunchAgents/` (RunAtLoad + KeepAlive). macOS privacy protection (TCC) blocks
launchd jobs from `~/Documents` unless the binary was granted access, and uv's Python is
not, so the agent runs `backend/scripts/serve.py` with a dedicated venv built on Homebrew
Python (`~/Library/Application Support/co.soclose.elninowatch/venv`, synced from `uv.lock`
on every start). Logs go to `data/elnino.log`. If the agent loops with exit code 78
(EX_CONFIG), that Python lost its Files and Folders permission: grant it in System Settings
> Privacy & Security, or set `ELNINO_AGENT_PYTHON` to a Python that has it.
