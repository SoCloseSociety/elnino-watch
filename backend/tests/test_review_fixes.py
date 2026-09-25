"""Regression tests for the 2026-09-24 correctness review (one per fix)."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("SCHEDULER", "false")

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db
from app.collectors import maritime as M
from app.collectors import official as O
from app.collectors.base import Collector, run_collector


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def ev(ext_id: str, **kw) -> dict:
    return {"ext_id": ext_id, "category": "flood", "lat": 1.0, "lon": 2.0, **kw}


# ---------------------------------------------------------------- replace_events


def test_replace_events_refuses_to_wipe_on_empty_fetch():
    db.replace_events("gdacs", [ev("a"), ev("b")])
    with pytest.raises(db.EmptyReplace):
        db.replace_events("gdacs", [])
    assert {r["ext_id"] for r in db.query("SELECT ext_id FROM events")} == {"a", "b"}
    # an explicitly allowed empty list (e.g. no bleaching alert anywhere) does clear
    db.replace_events("gdacs", [], allow_empty=True)
    assert db.query("SELECT * FROM events") == []


def test_replace_events_is_atomic_on_a_bad_row():
    db.replace_events("eonet", [ev("a")])
    with pytest.raises(KeyError):
        db.replace_events("eonet", [ev("b"), {"ext_id": "broken"}])  # no category
    assert [r["ext_id"] for r in db.query("SELECT ext_id FROM events")] == ["a"]


def test_replace_events_scope_keeps_unanswered_ids():
    db.replace_events("crw_vs", [ev("west"), ev("east")])
    # only "west" answered this time, and it is no longer in alert
    db.replace_events("crw_vs", [], allow_empty=True, scope_ext_ids=["west"])
    assert [r["ext_id"] for r in db.query("SELECT ext_id FROM events")] == ["east"]


async def test_crw_failed_station_keeps_its_event(monkeypatch):
    db.replace_events("crw_vs", [ev("east_gulf_of_thailand", category="bleaching"),
                                 ev("west_gulf_of_thailand", category="bleaching")])

    fix = Path(__file__).parent / "fixtures" / "maritime"
    west = (fix / "crw_west_gulf_of_thailand.txt").read_text()

    class FakeCtx:
        async def get(self, url):
            if "west_gulf" in url:
                return httpx.Response(200, text=west, request=httpx.Request("GET", url))
            raise httpx.ConnectError("down")

    monkeypatch.setattr(M, "CRW_STATIONS", ("west_gulf_of_thailand", "east_gulf_of_thailand"))
    ctx = FakeCtx()
    ctx.notes = {}
    await M.CoralReefWatch().collect(ctx)
    ids = {r["ext_id"] for r in db.query("SELECT ext_id FROM events WHERE source='crw_vs'")}
    assert "east_gulf_of_thailand" in ids  # failed station: previous event kept


# ---------------------------------------------------------------- marine forecast flag


def test_marine_forecast_flag_uses_bangkok_date(monkeypatch):
    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 24, 20, 0, tzinfo=UTC)  # = 25 Sep 03:00 in Bangkok

    monkeypatch.setattr(M, "datetime", Fixed)
    payload = {"latitude": 9.5, "longitude": 100.1,
               "hourly": {"time": ["2026-09-25T00:00", "2026-09-26T00:00"],
                          "wave_height": [0.3, 0.4], "sea_surface_temperature": [30.0, 30.1],
                          "swell_wave_height": [0.2, 0.2]},
               "daily": {"time": ["2026-09-25", "2026-09-26"], "wave_height_max": [0.5, 0.6]}}
    rows = {r["ts"]: r for r in M.parse_marine(payload)["rows"] if r["series"] == "samui_wave_height"}
    assert rows["2026-09-25"]["meta"]["forecast"] is False  # today on Samui
    assert rows["2026-09-26"]["meta"]["forecast"] is True


# ---------------------------------------------------------------- RSS dates


def test_rss_naive_date_is_utc_and_bad_date_does_not_drop_feed():
    rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
    <item><title>El Nino a</title><link>https://x/a</link><pubDate>2026-09-20 10:00</pubDate></item>
    <item><title>El Nino b</title><link>https://x/b</link><pubDate>not a date at all</pubDate></item>
    </channel></rss>"""
    rows = {r["url"]: r for r in O.parse_rss(rss, "NOAA")}
    assert rows["https://x/a"]["published_at"] == "2026-09-20T10:00:00+00:00"
    assert rows["https://x/b"]["published_at"] is None


# ---------------------------------------------------------------- run timeout


class Hang(Collector):
    name, title, category, provider = "t_hang", "hang", "news", "test"
    homepage = endpoint = "https://example.invalid"
    interval_s = 60

    async def collect(self, ctx):
        await asyncio.sleep(3600)
        return 0


class SockTimeout(Hang):
    name = "t_sock"

    async def collect(self, ctx):
        raise TimeoutError("timed out")  # e.g. urllib FTP socket timeout


async def test_hung_collector_is_cancelled_and_recorded():
    async with httpx.AsyncClient() as c:
        res = await run_collector(Hang(), c, timeout_s=0.1)
        res2 = await run_collector(SockTimeout(), c, timeout_s=10)
    assert not res["ok"]
    runs = {r["source"]: r for r in db.query("SELECT * FROM source_runs")}
    assert "exceeded" in runs["t_hang"]["error"]
    assert "exceeded" not in runs["t_sock"]["error"] and not res2["ok"]


# ---------------------------------------------------------------- API


def test_latest_ignores_forecast_rows():
    from app.main import app

    db.upsert_observations("openmeteo_marine", [
        {"series": "samui_wave_height", "ts": "2020-01-01", "value": 1.0},
        {"series": "samui_wave_height", "ts": "2020-01-02", "value": 2.0},
        {"series": "samui_wave_height", "ts": "2999-01-01", "value": 9.0},
    ])
    rows = TestClient(app).get("/api/latest").json()
    r = next(x for x in rows if x["series"] == "samui_wave_height")
    assert (r["ts"], r["value"], r["prev_value"]) == ("2020-01-02", 2.0, 1.0)


def test_spa_does_not_serve_files_outside_dist():
    from app import main

    if not main.DIST.is_dir():
        pytest.skip("frontend/dist not built")
    c = TestClient(main.app)
    for p in ("/..%2F..%2Fbackend%2Fpyproject.toml", "/../../backend/pyproject.toml",
              "/%2e%2e/%2e%2e/backend/pyproject.toml"):
        r = c.get(p)
        assert "elnino-watch" not in r.text
    assert c.get("/api/nope").status_code == 404
