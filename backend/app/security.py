"""Public-deployment hardening: admin gate, security headers, CSP, no API docs.

Installed by app.main (`security.install(app)`). Everything here reads `settings` at
request time, so tests can flip `settings.public_mode` without rebuilding the app.

Local mode (public_mode=false, the default): behaviour unchanged except the baseline
security headers (nosniff, referrer policy, ...) that never break anything.

Public mode (PUBLIC_MODE=true, a public deployment behind nginx):
- Every /api request that is not GET/HEAD/OPTIONS needs `X-Admin-Token: <admin_token>`
  (constant-time compare), else 403 JSON. Empty admin_token = nobody is admin.
- Admin-only GETs (they make the server hit upstreams on demand): ADMIN_GET_PATHS.
- `GET /api/preparedness/state` is the owner's household checklist: visitors get a
  404, which the Prep page treats as "no server copy" and falls back to its own
  localStorage (so each browser keeps its own checklist and never sees the owner's).
- `GET /api/briefing` builds on demand only when no briefing exists yet; that first
  build is single-flight (one LLM call, the other requests wait for its result).
- `GET /api/layers` answers from a 60 s shared response cache (single-flight), so a
  failing upstream (not cached by layers_api) is not hammered once per visitor.
- /docs, /redoc, /openapi.json answer 404.
- A Content-Security-Policy that allows exactly what the frontend loads (CSP below);
  the inline theme script of index.html is allowed by its sha256 hash, computed from
  frontend/dist/index.html at request time (cached on the file's mtime).
- `GET /api/access` -> {public_mode, admin} lets the frontend hide admin-only buttons.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import re
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from .config import ROOT, settings

log = logging.getLogger(__name__)

ADMIN_HEADER = "X-Admin-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# GETs that trigger heavy upstream work on demand: admin-only in public mode.
ADMIN_GET_PATHS = frozenset({"/api/layers/verify"})
# Owner-private GETs: visitors get 404 (the frontend then uses its browser copy).
PRIVATE_GET_PATHS = frozenset({"/api/preparedness/state"})
# Owner-private status documents (the same data as PRIVATE_GET_PATHS, reachable through the
# generic status routes): stripped from GET /api/status and 404 on GET /api/status/<key>
# for visitors, so the household numbers never leak through the side door.
PRIVATE_STATUS_KEYS = frozenset({"prep_state"})
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"})
# Shared response cache (public mode only): path -> seconds.
CACHED_GET_PATHS = {"/api/layers": 60.0}

DIST_INDEX = ROOT / "frontend" / "dist" / "index.html"

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",
    "Permissions-Policy": ("accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
                           "magnetometer=(), microphone=(), payment=(), usb=(), "
                           "interest-cohort=()"),
}

# What the frontend actually loads (grep frontend/src + backend layer/webcam URLs):
# - map tiles fetched by MapLibre (fetch -> connect-src): OSM + Esri base maps
#   (frontend/src/lib/geo.ts), NASA GIBS overlays + legends, RainViewer radar tiles
#   (host comes from the RainViewer API, today tilecache.rainviewer.com);
# - MapLibre runs its worker from a blob: URL (worker-src blob:);
# - images: feed item thumbnails from any news site, GIBS legends, webcam stills
#   (img-src https:);
# - webcam embeds offered by their owners: YouTube (nocookie) and the Windy player;
# - style-src 'unsafe-inline': MapLibre and Recharts set inline styles.
CSP_SOURCES: dict[str, list[str]] = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],  # + sha256 of the inline scripts of index.html
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "font-src": ["'self'", "data:"],
    "connect-src": ["'self'", "https://tile.openstreetmap.org",
                    "https://server.arcgisonline.com", "https://gibs.earthdata.nasa.gov",
                    "https://*.rainviewer.com"],
    "worker-src": ["'self'", "blob:"],
    "child-src": ["'self'", "blob:"],
    "frame-src": ["https://www.youtube-nocookie.com", "https://www.youtube.com",
                  "https://webcams.windy.com", "https://www.windy.com"],
    "media-src": ["'self'", "https:"],
    "manifest-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'self'"],
}

_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
                            re.DOTALL | re.IGNORECASE)
_hash_cache: tuple[float, list[str]] | None = None


def inline_script_hashes(index: Path = DIST_INDEX) -> list[str]:
    """'sha256-...' for every inline <script> of the built index.html (cached on mtime)."""
    global _hash_cache
    try:
        mtime = index.stat().st_mtime
    except OSError:
        return []
    if _hash_cache and _hash_cache[0] == mtime:
        return _hash_cache[1]
    html = index.read_text(encoding="utf-8")
    hashes = [
        "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"
        for s in _INLINE_SCRIPT.findall(html)
    ]
    _hash_cache = (mtime, hashes)
    return hashes


def content_security_policy(index: Path = DIST_INDEX) -> str:
    parts = []
    for directive, sources in CSP_SOURCES.items():
        if directive == "script-src":
            sources = sources + inline_script_hashes(index)
        parts.append(f"{directive} {' '.join(sources)}")
    return "; ".join(parts)


def is_admin(request: Request) -> bool:
    """Constant-time check of the X-Admin-Token header. No token configured = no admin."""
    expected = settings.admin_token
    got = request.headers.get(ADMIN_HEADER, "")
    if not expected or not got:
        return False
    return hmac.compare_digest(got.encode("utf-8"), expected.encode("utf-8"))


def _forbidden(why: str) -> JSONResponse:
    return JSONResponse({"detail": f"admin only in public mode: {why}"}, status_code=403)


def _guard(request: Request) -> Response | None:
    """Return a refusal for a public-mode request, or None to let it through."""
    path, method = request.url.path.rstrip("/") or "/", request.method.upper()
    if path in DOCS_PATHS:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    if not (path == "/api" or path.startswith("/api/")):
        return None
    if method not in SAFE_METHODS:
        return None if is_admin(request) else _forbidden(f"{method} needs {ADMIN_HEADER}")
    if path in ADMIN_GET_PATHS and not is_admin(request):
        return _forbidden(f"{path} triggers live upstream checks")
    if path in PRIVATE_GET_PATHS and not is_admin(request):
        return JSONResponse({"detail": "per-browser in public mode (kept in localStorage)"},
                            status_code=404)
    if (path.startswith("/api/status/") and path.rsplit("/", 1)[-1] in PRIVATE_STATUS_KEYS
            and not is_admin(request)):
        return JSONResponse({"detail": "no such status for visitors"}, status_code=404)
    return None


def hidden_status_keys(request: Request) -> frozenset[str]:
    """Status keys GET /api/status must leave out for this request (public mode, visitor)."""
    if settings.public_mode and not is_admin(request):
        return PRIVATE_STATUS_KEYS
    return frozenset()


_locks: dict[str, asyncio.Lock] = {}
_resp_cache: dict[str, tuple[float, int, bytes, str]] = {}


def _lock(key: str) -> asyncio.Lock:
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


async def _cached_get(request: Request, call_next, ttl: float) -> Response:
    key = str(request.url.path)
    async with _lock("cache:" + key):
        hit = _resp_cache.get(key)
        if hit and time.monotonic() - hit[0] < ttl:
            _, status, body, ctype = hit
        else:
            resp = await call_next(request)
            chunks = resp.body_iterator  # type: ignore[attr-defined]
            body = b"".join([chunk async for chunk in chunks])
            status, ctype = resp.status_code, resp.headers.get("content-type", "")
            if status == 200:
                _resp_cache[key] = (time.monotonic(), status, body, ctype)
    return Response(content=body, status_code=status, media_type=ctype or None,
                    headers={"Cache-Control": f"public, max-age={int(ttl)}"})


async def _briefing_get(request: Request, call_next) -> Response:
    """Build-on-demand only when none exists, and only once at a time (single flight)."""
    from . import briefing

    if briefing.current() is not None:
        return await call_next(request)
    async with _lock("briefing"):
        return await call_next(request)  # the handler re-checks: cached after the 1st build


def _decorate(request: Request, resp: Response) -> Response:
    for k, v in BASE_HEADERS.items():
        resp.headers.setdefault(k, v)
    if settings.public_mode:
        resp.headers.setdefault("Content-Security-Policy", content_security_policy())
        if request.url.scheme == "https":
            resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000")
    if resp.headers.get("content-type", "").startswith("text/html"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def _is_spa_path(path: str) -> bool:
    """A client-side route (no file extension, not API/assets/docs) -> index.html."""
    return (DIST_INDEX.is_file() and not path.startswith(("/api/", "/assets/"))
            and path != "/api" and path.rstrip("/") not in DOCS_PATHS
            and "." not in path.rsplit("/", 1)[-1])


def access(request: Request) -> dict:
    """Whether the server is in public mode and whether this request is admin."""
    return {"public_mode": settings.public_mode, "admin": is_admin(request),
            "admin_header": ADMIN_HEADER}


def install(app: FastAPI) -> None:
    """Add the middleware + GET /api/access. Call before the SPA catch-all route."""
    app.add_api_route("/api/access", access, methods=["GET"], include_in_schema=False)

    @app.middleware("http")
    async def _security(request: Request, call_next):
        if settings.public_mode:
            refusal = _guard(request)
            if refusal is not None:
                return _decorate(request, refusal)
            path = request.url.path
            if request.method == "GET" and path in CACHED_GET_PATHS:
                return _decorate(request, await _cached_get(request, call_next,
                                                            CACHED_GET_PATHS[path]))
            if request.method == "GET" and path == "/api/briefing":
                return _decorate(request, await _briefing_get(request, call_next))
        if request.method == "HEAD" and _is_spa_path(request.url.path):
            # the SPA route is GET-only (FastAPI adds no HEAD): answer like index.html
            return _decorate(request, Response(media_type="text/html"))
        return _decorate(request, await call_next(request))

    if settings.public_mode and not settings.admin_token:
        log.warning("PUBLIC_MODE without ADMIN_TOKEN: every admin action is refused")
