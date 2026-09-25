"""SQLite storage. One file, stdlib only, WAL mode.

Four shapes of data cover every source:
- observations : numeric time series (indices, buoy temps, local weather)
- feed_items   : anything a human reads (news, social posts, official bulletins)
- events       : geolocated happenings for the map (disasters, fires, storms)
- status       : latest snapshot documents keyed by name (CPC alert, IRI probs, local risk)
plus source_runs (health of every collector run) and alerts (what we told the owner).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from .config import settings

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    source TEXT NOT NULL, series TEXT NOT NULL, ts TEXT NOT NULL,
    value REAL, unit TEXT, meta TEXT,
    PRIMARY KEY (source, series, ts)
);
CREATE TABLE IF NOT EXISTS feed_items (
    source TEXT NOT NULL, ext_id TEXT NOT NULL,
    kind TEXT NOT NULL,            -- news | social | official | research
    title TEXT, summary TEXT, url TEXT, author TEXT, lang TEXT, image TEXT,
    published_at TEXT, fetched_at TEXT NOT NULL,
    lat REAL, lon REAL, tags TEXT,
    PRIMARY KEY (source, ext_id)
);
CREATE INDEX IF NOT EXISTS ix_feed_pub ON feed_items (published_at DESC);
CREATE TABLE IF NOT EXISTS events (
    source TEXT NOT NULL, ext_id TEXT NOT NULL,
    category TEXT NOT NULL,        -- cyclone | flood | drought | wildfire | heat | ...
    title TEXT, url TEXT, severity TEXT, lat REAL, lon REAL,
    started_at TEXT, updated_at TEXT, geometry TEXT, payload TEXT,
    seen_at TEXT,                  -- last fetch that listed this event (retention)
    PRIMARY KEY (source, ext_id)
);
CREATE TABLE IF NOT EXISTS status (
    key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
    ok INTEGER NOT NULL, items INTEGER DEFAULT 0, http_status INTEGER,
    latency_ms INTEGER, error TEXT, detail TEXT
);
CREATE INDEX IF NOT EXISTS ix_runs_source ON source_runs (source, id DESC);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL, level TEXT NOT NULL, kind TEXT NOT NULL,
    title TEXT NOT NULL, body TEXT, dedup_key TEXT UNIQUE, delivered TEXT
);
"""


class EmptyReplace(RuntimeError):
    """replace_events got an empty list for a source that has events: refusing to wipe
    the map on what is far more likely a partial / broken fetch than a quiet planet."""


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _migrate(c: sqlite3.Connection) -> None:
    cols = {r[1] for r in c.execute("PRAGMA table_info(events)")}
    if "seen_at" not in cols:
        c.execute("ALTER TABLE events ADD COLUMN seen_at TEXT")
        c.commit()


def _open(path) -> sqlite3.Connection:
    # timeout: another process (scripts/verify_sources.py --live-db) may hold the write lock
    c = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    _migrate(c)
    return c


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            settings.db_path.parent.mkdir(parents=True, exist_ok=True)
            _conn = _open(settings.db_path)
            _conn.execute("PRAGMA journal_mode=WAL")
        return _conn


def use_path(path) -> None:
    """Point the process at another database file (scripts that must not touch the live DB)."""
    global _conn
    with _lock:
        _conn = _open(path)
        _conn.execute("PRAGMA journal_mode=WAL")


def reset_for_tests(path: str = ":memory:") -> None:
    global _conn
    with _lock:
        _conn = _open(path)


def _j(v: Any) -> str | None:
    return None if v is None else json.dumps(v, ensure_ascii=False, default=str)


def upsert_observations(source: str, rows: Iterable[dict]) -> int:
    """rows: {series, ts (ISO date or datetime), value, unit?, meta?}"""
    data = [
        (source, r["series"], r["ts"], r["value"], r.get("unit"), _j(r.get("meta")))
        for r in rows
    ]
    with _lock:
        c = conn()
        c.executemany(
            "INSERT INTO observations VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(source,series,ts) DO UPDATE SET value=excluded.value, "
            "unit=excluded.unit, meta=excluded.meta",
            data,
        )
        c.commit()
    return len(data)


def upsert_feed_items(source: str, rows: Iterable[dict]) -> int:
    """rows: {ext_id, kind, title, summary?, url?, author?, lang?, image?,
    published_at?, lat?, lon?, tags? (list)}"""
    fetched = now_iso()
    data = [
        (
            source, r["ext_id"], r["kind"], r.get("title"), r.get("summary"), r.get("url"),
            r.get("author"), r.get("lang"), r.get("image"), r.get("published_at"), fetched,
            r.get("lat"), r.get("lon"), _j(r.get("tags")),
        )
        for r in rows
    ]
    with _lock:
        c = conn()
        c.executemany(
            "INSERT INTO feed_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source,ext_id) DO UPDATE SET title=excluded.title, "
            "summary=excluded.summary, url=excluded.url, image=excluded.image, "
            "published_at=COALESCE(excluded.published_at, feed_items.published_at), "
            "tags=excluded.tags, lat=excluded.lat, lon=excluded.lon",
            data,
        )
        c.commit()
    return len(data)


_EVENT_COLS = ("source, ext_id, category, title, url, severity, lat, lon, started_at, "
               "updated_at, geometry, payload, seen_at")


def _event_rows(source: str, rows: Iterable[dict]) -> list[tuple]:
    seen = now_iso()
    return [
        (
            source, r["ext_id"], r["category"], r.get("title"), r.get("url"), r.get("severity"),
            r.get("lat"), r.get("lon"), r.get("started_at"), r.get("updated_at"),
            _j(r.get("geometry")), _j(r.get("payload")), seen,
        )
        for r in rows
    ]


def _write_events(c: sqlite3.Connection, data: list[tuple]) -> None:
    c.executemany(
        f"INSERT INTO events ({_EVENT_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(source,ext_id) DO UPDATE SET category=excluded.category, "
        "title=excluded.title, url=excluded.url, severity=excluded.severity, "
        "lat=excluded.lat, lon=excluded.lon, updated_at=excluded.updated_at, "
        "geometry=excluded.geometry, payload=excluded.payload, seen_at=excluded.seen_at",
        data,
    )


def upsert_events(source: str, rows: Iterable[dict]) -> int:
    """rows: {ext_id, category, title, url?, severity? (green|orange|red|info),
    lat, lon, started_at?, updated_at?, geometry? (GeoJSON), payload? (dict)}"""
    data = _event_rows(source, rows)
    with _lock:
        c = conn()
        try:
            _write_events(c, data)
            c.commit()
        except Exception:
            c.rollback()
            raise
    return len(data)


def replace_events(source: str, rows: list[dict], *, allow_empty: bool = False,
                   scope_ext_ids: Iterable[str] | None = None) -> int:
    """For sources that publish the full current list (GDACS, EONET open events):
    drop what is no longer listed so the map never shows a closed event.

    One transaction under the lock: readers never see the half-replaced table.
    `scope_ext_ids` limits the delete to the ids this fetch was authoritative for
    (e.g. the CRW stations that answered), so a partial fetch keeps the rest.
    An empty `rows` raises EmptyReplace unless `allow_empty`: a broken fetch must
    not silently clear the map."""
    data = _event_rows(source, rows)
    scope = None if scope_ext_ids is None else list(scope_ext_ids)
    with _lock:
        c = conn()
        if not data and not allow_empty:
            n = c.execute("SELECT COUNT(*) FROM events WHERE source=?", (source,)).fetchone()[0]
            if n:
                raise EmptyReplace(f"{source}: fetch returned 0 events, keeping the {n} stored")
        try:
            if scope is None:
                c.execute("DELETE FROM events WHERE source=?", (source,))
            elif scope:
                c.execute(
                    f"DELETE FROM events WHERE source=? AND ext_id IN "
                    f"({','.join('?' * len(scope))})", (source, *scope))
            _write_events(c, data)
            c.commit()
        except Exception:
            c.rollback()
            raise
    return len(data)


def set_status(key: str, value: Any) -> None:
    with _lock:
        c = conn()
        c.execute(
            "INSERT INTO status VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value, updated_at=excluded.updated_at",
            (key, _j(value), now_iso()),
        )
        c.commit()


def get_status(key: str) -> dict | None:
    with _lock:
        row = conn().execute("SELECT value, updated_at FROM status WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    return {"value": json.loads(row["value"]), "updated_at": row["updated_at"]}


def record_run(source: str, started_at: str, ok: bool, items: int = 0, http_status: int | None = None,
               latency_ms: int | None = None, error: str | None = None, detail: Any = None) -> None:
    with _lock:
        c = conn()
        c.execute(
            "INSERT INTO source_runs (source, started_at, finished_at, ok, items, http_status, "
            "latency_ms, error, detail) VALUES (?,?,?,?,?,?,?,?,?)",
            (source, started_at, now_iso(), int(ok), items, http_status, latency_ms, error,
             _j(detail)),
        )
        # keep the last 200 runs per source
        c.execute(
            "DELETE FROM source_runs WHERE source=? AND id NOT IN "
            "(SELECT id FROM source_runs WHERE source=? ORDER BY id DESC LIMIT 200)",
            (source, source),
        )
        c.commit()


def add_alert(level: str, kind: str, title: str, body: str, dedup_key: str) -> int | None:
    """Returns the new alert id, or None if this dedup_key was already raised."""
    with _lock:
        c = conn()
        cur = c.execute(
            "INSERT OR IGNORE INTO alerts (created_at, level, kind, title, body, dedup_key) "
            "VALUES (?,?,?,?,?,?)",
            (now_iso(), level, kind, title, body, dedup_key),
        )
        c.commit()
        return cur.lastrowid if cur.rowcount else None


def query(sql: str, params: tuple = ()) -> list[dict]:
    with _lock:
        rows = conn().execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("meta", "tags", "geometry", "payload", "detail", "value"):
            if k in d and isinstance(d[k], str) and d[k][:1] in "[{":
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    pass
        out.append(d)
    return out


# ------------------------------------------------------------------ retention

FEED_KEEP_DAYS = 180       # news / social / research; kind=official is kept forever
EVENT_CLOSED_DAYS = 30     # an event no fetch has listed for this long is closed
HOURLY_KEEP_DAYS = 365     # hourly buoy points older than this become one daily mean
HOURLY_SERIES_LIKE = "tao_%"  # the only hourly observation series (TAO/TRITON buoys)


def downsample_hourly(now: datetime | None = None) -> dict:
    """Observations retention: hourly TAO/TRITON buoy points older than HOURLY_KEEP_DAYS
    are replaced by ONE daily mean per (source, series, day): ts = YYYY-MM-DD, value = the
    mean of that day's hourly values, meta {n, downsample: "daily_mean", unit kept}. Daily
    and monthly series (every index, ERA5, gauges) are never touched, so the history stays
    complete; only the hour-by-hour detail of old buoy data is folded (~1,150 rows/day,
    ~60 MB a year otherwise). Idempotent: daily rows have a 10-character ts and are skipped."""
    from datetime import timedelta

    now = now or datetime.now(UTC)
    cut = (now - timedelta(days=HOURLY_KEEP_DAYS)).replace(microsecond=0).isoformat()
    with _lock:
        c = conn()
        days = c.execute(
            "SELECT source, series, substr(ts, 1, 10) AS d, AVG(value) AS v, MAX(unit) AS unit, "
            "COUNT(*) AS n FROM observations WHERE series LIKE ? AND length(ts) > 10 "
            "AND ts < ? AND value IS NOT NULL GROUP BY source, series, d",
            (HOURLY_SERIES_LIKE, cut)).fetchall()
        for source, series, d, v, unit, n in days:
            meta = json.dumps({"n": n, "downsample": "daily_mean"})
            c.execute("INSERT OR REPLACE INTO observations (source, series, ts, value, unit, meta) "
                      "VALUES (?, ?, ?, ?, ?, ?)", (source, series, d, round(v, 4), unit, meta))
        deleted = c.execute(
            "DELETE FROM observations WHERE series LIKE ? AND length(ts) > 10 AND ts < ?",
            (HOURLY_SERIES_LIKE, cut)).rowcount
        c.commit()
    return {"days": len(days), "hourly_rows": deleted, "cutoff": cut}


def prune(now: datetime | None = None) -> dict:
    """Retention. source_runs is already capped per source in record_run."""
    from datetime import timedelta

    now = now or datetime.now(UTC)
    feed_cut = (now - timedelta(days=FEED_KEEP_DAYS)).replace(microsecond=0).isoformat()
    ev_cut = (now - timedelta(days=EVENT_CLOSED_DAYS)).replace(microsecond=0).isoformat()
    with _lock:
        c = conn()
        f = c.execute(
            "DELETE FROM feed_items WHERE kind != 'official' "
            "AND COALESCE(published_at, fetched_at) < ?", (feed_cut,)).rowcount
        # seen_at is NULL for rows written before the column existed: fall back to dates
        e = c.execute(
            "DELETE FROM events WHERE COALESCE(seen_at, updated_at, started_at) < ?",
            (ev_cut,)).rowcount
        c.commit()
    hourly = downsample_hourly(now)
    return {"feed_items": f, "events": e, "feed_cutoff": feed_cut, "events_cutoff": ev_cut,
            "observations_hourly": hourly["hourly_rows"], "observations_days": hourly["days"],
            "hourly_cutoff": hourly["cutoff"]}


def vacuum() -> None:
    with _lock:
        c = conn()
        c.commit()
        c.execute("VACUUM")
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
