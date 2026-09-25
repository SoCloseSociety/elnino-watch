"""HTTP API + static dashboard. Contract is documented in ../../CLAUDE.md (API section)."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import briefing, db, scheduler, security
from .collectors import all_collectors, source_report
from .config import ROOT, settings
from .local import provenance as P
from .local.collectors import today_bkk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# app.local registers the Koh Samui risk engine + alert hooks on import.
with contextlib.suppress(ModuleNotFoundError):
    importlib.import_module("app.local")


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    db.conn()
    task = asyncio.create_task(scheduler.loop()) if settings.scheduler else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="El Nino Watch", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5211", "http://127.0.0.1:5211"],
    allow_methods=["*"], allow_headers=["*"],
)
# Public-mode admin gate + security headers/CSP (app/security.py); before the SPA route.
security.install(app)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "collectors": len(all_collectors()), "home": settings.home_name}


# ------------------------------------------------------------------ filter helpers


def _csv(v: str | None) -> list[str]:
    """'a,b , c' -> ['a', 'b', 'c'] (every list filter takes a comma list)."""
    return [x.strip() for x in (v or "").split(",") if x.strip()]


class _Where:
    def __init__(self, base: str = "1=1") -> None:
        self.clauses: list[str] = [base]
        self.params: list = []

    def add(self, clause: str, *params) -> None:
        self.clauses.append(clause)
        self.params += params

    def any_of(self, col: str, raw: str | None) -> None:
        vals = _csv(raw)
        if vals:
            self.add(f"{col} IN ({','.join('?' * len(vals))})", *vals)

    @property
    def sql(self) -> str:
        return " AND ".join(self.clauses)


def _pair(raw: str, n: int, name: str) -> list[float]:
    try:
        vals = [float(x) for x in raw.split(",")]
    except ValueError:
        raise HTTPException(422, f"{name}: expected {n} comma-separated numbers") from None
    if len(vals) != n:
        raise HTTPException(422, f"{name}: expected {n} comma-separated numbers")
    return vals


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _counts(sql: str, params: list, limit: int = 50) -> list[dict]:
    return [{"value": r["v"], "count": r["n"]} for r in db.query(
        sql + " GROUP BY v ORDER BY n DESC, v LIMIT ?", (*params, limit))]


# ------------------------------------------------------------------ series


@app.get("/api/series/catalog")
def series_catalog(source: str | None = None, category: str | None = None,
                   q: str | None = None) -> list[dict]:
    """Every stored series. Filters: source (comma list), category (collector category,
    comma list: ocean_index, maritime, local, ...), q (substring of the series name)."""
    w = _Where()
    w.any_of("source", source)
    cats = set(_csv(category))
    if cats:
        names = [c.name for c in all_collectors() if c.category in cats]
        if not names:
            return []
        w.add(f"source IN ({','.join('?' * len(names))})", *names)
    if q:
        w.add("series LIKE ?", f"%{q}%")
    return db.query(
        "SELECT source, series, unit, COUNT(*) AS points, MIN(ts) AS first, MAX(ts) AS last "
        f"FROM observations WHERE {w.sql} GROUP BY source, series ORDER BY source, series",
        tuple(w.params))


@app.get("/api/series")
def series(source: str, series: str, since: str | None = None, until: str | None = None,
           limit: int = Query(5000, ge=1, le=100000),
           downsample: str | None = None) -> dict:
    """Points oldest -> newest (the newest `limit` of them).

    downsample: `daily` = one mean point per day (ts = YYYY-MM-DD, meta.n = points
    averaged), or an integer N = every Nth point (the newest point is always kept)."""
    w = _Where("source=? AND series=?")
    w.params += [source, series]
    if since:
        w.add("ts >= ?", since)
    if until:
        w.add("ts <= ?", until)
    if downsample == "daily":
        rows = db.query(
            "SELECT substr(ts, 1, 10) AS ts, ROUND(AVG(value), 4) AS value, MAX(unit) AS unit, "
            f"COUNT(*) AS n FROM observations WHERE {w.sql} GROUP BY substr(ts, 1, 10) "
            "ORDER BY ts DESC LIMIT ?", (*w.params, limit))
        rows = [{"ts": r["ts"], "value": r["value"], "unit": r["unit"],
                 "meta": {"n": r["n"], "downsample": "daily_mean"}} for r in rows]
    elif downsample:
        try:
            every = int(downsample)
        except ValueError:
            raise HTTPException(422, "downsample: 'daily' or an integer N") from None
        if every < 1:
            raise HTTPException(422, "downsample: N must be >= 1")
        rows = db.query(
            "SELECT ts, value, unit, meta FROM (SELECT ts, value, unit, meta, "
            "ROW_NUMBER() OVER (ORDER BY ts DESC) AS rn FROM observations "
            f"WHERE {w.sql}) WHERE (rn - 1) % ? = 0 ORDER BY ts DESC LIMIT ?",
            (*w.params, every, limit))
    else:
        rows = db.query(f"SELECT ts, value, unit, meta FROM observations WHERE {w.sql} "
                        "ORDER BY ts DESC LIMIT ?", (*w.params, limit))
    rows.reverse()
    return {"source": source, "series": series, "points": rows}


SERIES_BATCH_MAX = 60


@app.get("/api/series/batch")
def series_batch(keys: str, since: str | None = None, until: str | None = None,
                 limit: int = Query(5000, ge=1, le=100000),
                 downsample: str | None = None) -> dict:
    """Several series in ONE request: `keys=source:series,source:series,...` (<= 60), the
    other parameters as in GET /api/series and applied to every key. Answers
    `{items: [{source, series, points}], missing: ["source:series"]}` (a key with no stored
    point is listed in `missing`, with an empty `points` entry too).

    Why: the Indices page draws ~80 series; one request each blew through the public
    nginx rate limit (10 r/s, burst 40) and half the charts showed "--" (QA, 24 Sep 2026)."""
    parsed: list[tuple[str, str]] = []
    for raw in _csv(keys):
        source, sep, name = raw.partition(":")
        if not sep or not source or not name:
            raise HTTPException(422, f"keys: expected source:series, got {raw!r}")
        if (source, name) not in parsed:
            parsed.append((source, name))
    if not parsed:
        raise HTTPException(422, "keys: at least one source:series")
    if len(parsed) > SERIES_BATCH_MAX:
        raise HTTPException(422, f"keys: at most {SERIES_BATCH_MAX} series per request")
    items = [series(source=s, series=n, since=since, until=until, limit=limit,
                    downsample=downsample) for s, n in parsed]
    return {"items": items, "missing": [f"{it['source']}:{it['series']}" for it in items
                                        if not it["points"]]}


@app.get("/api/latest")
def latest() -> list[dict]:
    """Latest NON-FORECAST point of every series, with the previous one for a delta.

    Forecast rows are left out, otherwise "latest" would be a value from next week
    presented as current: every row with ts in the future, and TODAY's daily row of the
    forecast-model sources (Open-Meteo samui / marine: the day is not over, its total or
    maximum still contains forecast hours). A series that only has future rows does not
    appear here (use /api/series). Each row carries kind / valid_for / tz / unit_label
    (see app/local/provenance.py)."""
    today = today_bkk()
    model_daily = sorted(P.MODEL_DAILY_SOURCES)
    rows = db.query(
        f"""
        SELECT o.source, o.series, o.ts, o.value, o.unit,
          (SELECT value FROM observations p WHERE p.source=o.source AND p.series=o.series
             AND p.ts < o.ts ORDER BY p.ts DESC LIMIT 1) AS prev_value
        FROM observations o
        JOIN (SELECT source, series, MAX(ts) AS mts FROM observations WHERE ts <= ?
                AND NOT (source IN ({",".join("?" * len(model_daily))}) AND ts >= ?)
              GROUP BY source, series) m
          ON m.source=o.source AND m.series=o.series AND m.mts=o.ts
        ORDER BY o.source, o.series
        """,
        (db.now_iso(), *model_daily, today.isoformat()),
    )
    return [P.annotate_point(r, today=today) for r in rows]


STATUS_LIST_MAX_BYTES = 12_000  # heavier documents are listed without their value


@app.get("/api/status")
def status_all(request: Request, full: bool = False) -> dict:
    """Each entry: {value, updated_at, kind} (kind: see provenance.STATUS_KINDS; null =
    derived by this app, e.g. local_risk, briefing). Owner-private documents
    (security.PRIVATE_STATUS_KEYS) are left out for visitors in public mode.

    Documents over STATUS_LIST_MAX_BYTES (webcams, place forecasts, the ERA5 history...)
    are listed with `value: null`, `omitted: true` and their `bytes`: the listing was
    460 KB otherwise. `?full=1` returns every value; `GET /api/status/{key}` always does."""
    hidden = security.hidden_status_keys(request)
    rows = db.query("SELECT key, value, updated_at, length(value) AS bytes FROM status")
    out = {}
    for r in rows:
        if r["key"] in hidden:
            continue
        entry = {"value": r["value"], "updated_at": r["updated_at"],
                 "kind": P.STATUS_KINDS.get(r["key"]), "bytes": r["bytes"]}
        if not full and r["bytes"] > STATUS_LIST_MAX_BYTES:
            entry |= {"value": None, "omitted": True,
                      "url": f"/api/status/{r['key']}"}
        out[r["key"]] = entry
    return out


@app.get("/api/status/{key}")
def status_one(key: str) -> dict:
    s = db.get_status(key)
    if s is None:
        raise HTTPException(404, f"no status '{key}' yet")
    return s | {"kind": P.STATUS_KINDS.get(key)}


# ------------------------------------------------------------------ feed

_FEED_TIME = "COALESCE(published_at, fetched_at)"
_FEED_TAG = ("EXISTS (SELECT 1 FROM json_each(feed_items.tags) jt "
             "WHERE jt.value IN ({}))")


def _feed_where(kind=None, source=None, lang=None, tag=None, q=None, since=None, until=None,
                before=None, has_geo=None, skip: str | None = None) -> _Where:
    """`skip` leaves one dimension out (facet counts ignore their own filter)."""
    w = _Where()
    for dim, col, raw in (("kind", "kind", kind), ("source", "source", source),
                          ("lang", "lang", lang)):
        if dim != skip:
            w.any_of(col, raw)
    tags = _csv(tag)
    if tags and skip != "tag":
        w.add(_FEED_TAG.format(",".join("?" * len(tags))), *tags)
    if q:
        w.add("(title LIKE ? OR summary LIKE ? OR author LIKE ?)", f"%{q}%", f"%{q}%", f"%{q}%")
    if since:
        w.add(f"{_FEED_TIME} >= ?", since)
    if until:
        w.add(f"{_FEED_TIME} <= ?", until)
    if before:
        w.add(f"{_FEED_TIME} < ?", before)
    if has_geo is True:
        w.add("lat IS NOT NULL AND lon IS NOT NULL")
    elif has_geo is False:
        w.add("(lat IS NULL OR lon IS NULL)")
    return w


@app.get("/api/feed")
def feed(
    kind: str | None = None, source: str | None = None, q: str | None = None,
    lang: str | None = None, tag: str | None = None, since: str | None = None,
    until: str | None = None, before: str | None = None, has_geo: bool | None = None,
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
) -> list[dict]:
    """kind / source / lang / tag take comma lists (tag matches ANY listed tag); since /
    until / before compare ISO strings against published_at (else fetched_at)."""
    w = _feed_where(kind, source, lang, tag, q, since, until, before, has_geo)
    return db.query(f"SELECT * FROM feed_items WHERE {w.sql} ORDER BY {_FEED_TIME} DESC "
                    "LIMIT ? OFFSET ?", (*w.params, limit, offset))


@app.get("/api/feed/facets")
def feed_facets(
    kind: str | None = None, source: str | None = None, q: str | None = None,
    lang: str | None = None, tag: str | None = None, since: str | None = None,
    until: str | None = None, before: str | None = None, has_geo: bool | None = None,
) -> dict:
    """Counts per kind / source / lang / tag (top 50) under the current filters. Each
    dimension ignores its own filter, so the chips of a selected facet stay visible."""
    args = (kind, source, lang, tag, q, since, until, before, has_geo)
    w = _feed_where(*args)
    total = db.query(f"SELECT COUNT(*) AS n FROM feed_items WHERE {w.sql}", tuple(w.params))
    out: dict = {"total": total[0]["n"]}
    for dim in ("kind", "source", "lang"):
        w = _feed_where(*args, skip=dim)
        out[dim] = _counts(f"SELECT {dim} AS v, COUNT(*) AS n FROM feed_items WHERE {w.sql}",
                           w.params)
    w = _feed_where(*args, skip="tag")
    out["tag"] = _counts("SELECT jt.value AS v, COUNT(*) AS n FROM feed_items, "
                         f"json_each(feed_items.tags) jt WHERE {w.sql}", w.params)
    return out


# ------------------------------------------------------------------ events

_EV_TIME = "COALESCE(updated_at, started_at)"


def _events_where(category=None, source=None, severity=None, since=None, bbox=None,
                  near=None, radius_km=None, skip: str | None = None
                  ) -> tuple[_Where, tuple[float, float, float] | None]:
    w = _Where("lat IS NOT NULL AND lon IS NOT NULL")
    for dim, raw in (("category", category), ("source", source), ("severity", severity)):
        if dim != skip:
            w.any_of(dim, raw)
    if since:
        w.add(f"{_EV_TIME} >= ?", since)
    if bbox:
        min_lon, min_lat, max_lon, max_lat = _pair(bbox, 4, "bbox")
        w.add("lat BETWEEN ? AND ?", min_lat, max_lat)
        if min_lon <= max_lon:
            w.add("lon BETWEEN ? AND ?", min_lon, max_lon)
        else:  # crosses the antimeridian, e.g. 170,-10,-170,10
            w.add("(lon >= ? OR lon <= ?)", min_lon, max_lon)
    circle = None
    if near:
        lat, lon = _pair(near, 2, "near")
        r = float(radius_km or settings.home_radius_km)
        dlat = r / 111.0  # cheap SQL prefilter on latitude, exact distance in Python
        w.add("lat BETWEEN ? AND ?", lat - dlat, lat + dlat)
        circle = (lat, lon, r)
    return w, circle


def _in_circle(rows: list[dict], circle) -> list[dict]:
    if not circle:
        return rows
    lat, lon, r = circle
    out = []
    for e in rows:
        d = _km(lat, lon, e["lat"], e["lon"])
        if d <= r:
            e["distance_km"] = round(d, 1)
            out.append(e)
    return out


EVENTS_PAGE_DEFAULT = 500


@app.get("/api/events")
def events(category: str | None = None, source: str | None = None,
           severity: str | None = None, since: str | None = None, bbox: str | None = None,
           near: str | None = None, radius_km: float | None = Query(None, gt=0),
           limit: int | None = Query(None, ge=1, le=20000), paged: bool = False,
           offset: int = Query(0, ge=0)) -> list[dict] | dict:
    """category / source / severity take comma lists. bbox=minLon,minLat,maxLon,maxLat
    (minLon > maxLon crosses the antimeridian). near=lat,lon + radius_km (default: the
    home radius) adds distance_km. since compares updated_at (else started_at).

    Without `paged` the answer is the plain list (every matching row unless `limit` is
    given: the original contract). `paged=1` answers {total, limit, offset, items} with a
    default limit of EVENTS_PAGE_DEFAULT, newest first, for clients that page."""
    w, circle = _events_where(category, source, severity, since, bbox, near, radius_km)
    rows = _in_circle(db.query(f"SELECT * FROM events WHERE {w.sql} ORDER BY {_EV_TIME} DESC",
                               tuple(w.params)), circle)
    total = len(rows)
    if paged:
        limit = limit or EVENTS_PAGE_DEFAULT
        rows = rows[offset:offset + limit]
    elif limit:
        rows = rows[:limit]
    for e in rows:  # agency alert (bulletin) vs a direct detection (observed)
        e["kind"] = P.event_kind(e["source"])
    if paged:
        return {"total": total, "limit": limit, "offset": offset, "items": rows}
    return rows


@app.get("/api/events/facets")
def events_facets(category: str | None = None, source: str | None = None,
                  severity: str | None = None, since: str | None = None,
                  bbox: str | None = None, near: str | None = None,
                  radius_km: float | None = Query(None, gt=0)) -> dict:
    args = (category, source, severity, since, bbox, near, radius_km)
    out: dict = {}
    w, circle = _events_where(*args)
    out["total"] = len(_in_circle(db.query(f"SELECT lat, lon FROM events WHERE {w.sql}",
                                           tuple(w.params)), circle))
    for dim in ("category", "source", "severity"):
        w, circle = _events_where(*args, skip=dim)
        rows = _in_circle(db.query(f"SELECT {dim} AS v, lat, lon FROM events WHERE {w.sql}",
                                   tuple(w.params)), circle)
        counts: dict = {}
        for r in rows:
            counts[r["v"]] = counts.get(r["v"], 0) + 1
        out[dim] = [{"value": k, "count": n} for k, n in
                    sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))]
    return out


@app.get("/api/sources")
def sources(category: str | None = None, state: str | None = None) -> list[dict]:
    """category / state take comma lists; state includes `stale`."""
    cats, states = set(_csv(category)), set(_csv(state))
    return [r for r in source_report()
            if (not cats or r["category"] in cats) and (not states or r["state"] in states)]


@app.post("/api/sources/{name}/run")
async def run_source(name: str) -> dict:
    if name not in {c.name for c in all_collectors()}:
        raise HTTPException(404, "unknown source")
    return (await scheduler.run_all({name}))[0]


@app.post("/api/sources/verify")
async def verify_all() -> list[dict]:
    """Run every collector now. This IS the source verification: it hits the real endpoints."""
    return await scheduler.run_all()


@app.get("/api/briefing")
async def get_briefing() -> dict:
    """Deterministic briefing built from the DB (optionally rewritten by the LLM).
    Regenerated every 6 h and when the Koh Samui level changes; built on demand if none."""
    doc = briefing.current()
    if doc is None:
        doc = await briefing.refresh(force=True)
    return doc


@app.post("/api/briefing/refresh")
async def refresh_briefing() -> dict:
    return await briefing.refresh(force=True)


@app.get("/api/alerts")
def alerts(level: str | None = None, kind: str | None = None, since: str | None = None,
           limit: int = Query(50, ge=1, le=1000)) -> list[dict]:
    """level / kind take comma lists; since compares created_at."""
    w = _Where()
    w.any_of("level", level)
    w.any_of("kind", kind)
    if since:
        w.add("created_at >= ?", since)
    return db.query(f"SELECT * FROM alerts WHERE {w.sql} ORDER BY id DESC LIMIT ?",
                    (*w.params, limit))


# Optional routers owned by their domain: Koh Samui watch + preparedness, map layers.
# app.seo last but still BEFORE the SPA catch-all below: it owns GET / and the page paths
# (server-rendered <head> + crawler summary), /sitemap.xml, /robots.txt, /og/current.png.
for _mod in ("app.local.api", "app.layers_api", "app.cams_api", "app.places.api", "app.shopping.api",
             "app.analogs_api", "app.seo"):
    with contextlib.suppress(ModuleNotFoundError):
        app.include_router(importlib.import_module(_mod).router)


DIST = ROOT / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "unknown API route")
        f = DIST / path
        if path and f.is_file() and Path(f).resolve().is_relative_to(DIST.resolve()):
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
