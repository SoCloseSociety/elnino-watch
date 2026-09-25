"""Freshness (contract round 2), the `stale` source state, and retention."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta

os.environ.setdefault("SCHEDULER", "false")

import pytest
from fastapi.testclient import TestClient

from app import db
from app.collectors import all_collectors, source_state
from app.collectors.base import DAY, Collector

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


class _T(Collector):
    name, title, category, provider = "t_src", "t", "news", "test"
    homepage = endpoint = "https://example.invalid"
    interval_s = 3600


class Obs(_T):
    name = "t_obs"
    freshness_basis = "observations"
    max_age_s = 4 * DAY


class Feed(_T):
    name = "t_feed"
    freshness_basis = "feed"
    max_age_s = 2 * DAY


class Ev(_T):
    name = "t_ev"
    freshness_basis = "events"
    max_age_s = 3600


class Run(_T):
    name = "t_run"


def test_every_core_collector_declares_freshness():
    for c in all_collectors():
        mod = type(c).__module__.rsplit(".", 1)[-1]
        if mod in ("indices", "official", "maritime", "hazards", "news", "social"):
            assert c.max_age_s, c.name
            assert c.freshness_basis in ("observations", "feed", "events", "status", "run")


def test_observations_basis_ignores_forecast_rows():
    db.upsert_observations("t_obs", [{"series": "a", "ts": "2026-09-19", "value": 1},
                                     {"series": "a", "ts": "2026-10-01", "value": 2}])
    f = Obs.freshness(NOW)
    assert f["newest_data_at"] == "2026-09-19" and f["stale"]  # 5.5 d > 4 d
    assert f["age_s"] == int(5.5 * DAY) and f["basis"] == "observations"
    db.upsert_observations("t_obs", [{"series": "a", "ts": "2026-09-22", "value": 1}])
    assert not Obs.freshness(NOW)["stale"]


def test_feed_events_run_bases():
    db.upsert_feed_items("t_feed", [{"ext_id": "1", "kind": "news", "title": "x",
                                     "published_at": "2025-06-12T12:00:00+00:00"}])
    assert Feed.freshness(NOW)["stale"]
    db.upsert_events("t_ev", [{"ext_id": "1", "category": "flood", "lat": 0, "lon": 0,
                               "updated_at": (NOW - timedelta(minutes=10)).isoformat()}])
    assert not Ev.freshness(NOW)["stale"]
    assert Run.freshness(NOW) == {"newest_data_at": None, "max_age_s": 3 * 3600,
                                  "age_s": None, "stale": True, "basis": "run"}
    db.record_run("t_run", db.now_iso(), ok=True, items=3)
    assert not Run.freshness()["stale"]


def test_fetch_ok_but_old_data_is_stale_not_ok():
    db.upsert_feed_items("t_feed", [{"ext_id": "1", "kind": "official", "title": "x",
                                     "published_at": "2025-06-12T12:00:00+00:00"}])
    db.record_run("t_feed", db.now_iso(), ok=True, items=1)
    row = source_state(Feed())
    assert row["state"] == "stale"
    assert row["freshness"]["newest_data_at"] == "2025-06-12T12:00:00+00:00"
    db.upsert_feed_items("t_feed", [{"ext_id": "2", "kind": "official", "title": "y",
                                     "published_at": db.now_iso()}])
    assert source_state(Feed())["state"] == "ok"


def test_api_sources_rows_carry_freshness():
    from app.main import app

    rows = TestClient(app).get("/api/sources").json()
    oni = next(r for r in rows if r["name"] == "cpc_oni")
    assert set(oni["freshness"]) == {"newest_data_at", "max_age_s", "age_s", "stale", "basis"}
    assert oni["freshness"]["basis"] == "observations" and oni["state"] == "pending"


# ---------------------------------------------------------------- retention


def test_prune_keeps_official_and_recent():
    old = (NOW - timedelta(days=200)).isoformat()
    new = (NOW - timedelta(days=10)).isoformat()
    db.upsert_feed_items("s", [
        {"ext_id": "old_news", "kind": "news", "title": "a", "published_at": old},
        {"ext_id": "old_official", "kind": "official", "title": "b", "published_at": old},
        {"ext_id": "new_news", "kind": "news", "title": "c", "published_at": new},
    ])
    db.upsert_events("e", [{"ext_id": "gone", "category": "flood", "lat": 0, "lon": 0},
                           {"ext_id": "live", "category": "flood", "lat": 0, "lon": 0}])
    with db._lock:
        db.conn().execute("UPDATE events SET seen_at=? WHERE ext_id='gone'",
                          ((NOW - timedelta(days=31)).isoformat(),))
        db.conn().execute("UPDATE events SET seen_at=? WHERE ext_id='live'",
                          ((NOW - timedelta(days=2)).isoformat(),))
    out = db.prune(NOW)
    assert out["feed_items"] == 1 and out["events"] == 1
    assert {r["ext_id"] for r in db.query("SELECT ext_id FROM feed_items")} == {
        "old_official", "new_news"}
    assert [r["ext_id"] for r in db.query("SELECT ext_id FROM events")] == ["live"]


def test_seen_at_migration_on_old_db(tmp_path):
    p = tmp_path / "old.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE events (source TEXT NOT NULL, ext_id TEXT NOT NULL, category TEXT "
              "NOT NULL, title TEXT, url TEXT, severity TEXT, lat REAL, lon REAL, started_at "
              "TEXT, updated_at TEXT, geometry TEXT, payload TEXT, PRIMARY KEY (source, ext_id))")
    c.commit()
    c.close()
    db.reset_for_tests(str(p))
    db.upsert_events("s", [{"ext_id": "1", "category": "flood", "lat": 0, "lon": 0}])
    assert db.query("SELECT seen_at FROM events")[0]["seen_at"]


async def test_maintenance_records_status_and_vacuums(tmp_path):
    from app import scheduler

    db.reset_for_tests(str(tmp_path / "m.db"))
    doc = await scheduler.maintenance()
    assert doc["policy"]["feed_items_days"] == 180 and doc["last_vacuum"]
    assert db.get_status("maintenance")["value"]["pruned"] == {
        "feed_items": 0, "events": 0, "observations_hourly": 0, "observations_days": 0}
    assert "daily mean" in doc["policy"]["observations"]


def test_hourly_buoy_points_older_than_a_year_become_daily_means():
    old_day = (NOW - timedelta(days=400)).date().isoformat()
    recent_day = (NOW - timedelta(days=10)).date().isoformat()
    db.upsert_observations("tao_buoys", [
        {"series": "tao_1_sst", "ts": f"{old_day}T{h:02d}:00:00+00:00", "value": 27.0 + h / 10,
         "unit": "degC", "meta": {"lat": 0, "lon": -140}} for h in range(24)] + [
        {"series": "tao_1_sst", "ts": f"{recent_day}T{h:02d}:00:00+00:00", "value": 28.0}
        for h in range(3)] + [
        # a daily index and a monthly index far in the past: never touched
        {"series": "oni", "ts": "1997-12-15", "value": 2.37, "unit": "degC"},
        {"series": "world_sst_daily", "ts": "2024-01-01", "value": 20.5, "unit": "degC"}])
    out = db.prune(NOW)
    assert out["observations_hourly"] == 24 and out["observations_days"] == 1
    rows = db.query("SELECT ts, value, meta FROM observations WHERE series='tao_1_sst' ORDER BY ts")
    assert rows[0]["ts"] == old_day and rows[0]["value"] == pytest.approx(28.15, abs=1e-3)
    assert rows[0]["meta"] == {"n": 24, "downsample": "daily_mean"}
    assert len(rows) == 4 and all(len(r["ts"]) > 10 for r in rows[1:])  # recent hours kept
    assert db.query("SELECT COUNT(*) AS n FROM observations WHERE series IN ('oni', 'world_sst_daily')")[0]["n"] == 2
    # idempotent: a second pass finds nothing to fold and keeps the daily row
    out2 = db.prune(NOW)
    assert out2["observations_hourly"] == 0 and out2["observations_days"] == 0
    assert len(db.query("SELECT ts FROM observations WHERE series='tao_1_sst'")) == 4


def test_expected_stale_is_declared_and_reported():
    from app.collectors.official import ClimateGovEnsoBlog

    assert "2025-06-12" in ClimateGovEnsoBlog.expected_stale
    assert ClimateGovEnsoBlog.describe()["expected_stale"] == ClimateGovEnsoBlog.expected_stale
    db.upsert_feed_items("climategov_enso_blog", [
        {"ext_id": "1", "kind": "official", "title": "x", "published_at": "2025-06-12T12:00:00+00:00"}])
    db.record_run("climategov_enso_blog", db.now_iso(), ok=True, items=1)
    row = source_state(ClimateGovEnsoBlog())
    assert row["state"] == "stale" and row["expected_stale"]  # honest state, documented reason
    assert Feed.describe()["expected_stale"] is None


def test_verify_script_ignores_documented_silent_feeds_in_its_exit_code():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "verify_sources", Path(__file__).resolve().parents[1] / "scripts" / "verify_sources.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = [{"name": "a", "state": "ok"}, {"name": "b", "state": "stale", "expected_stale": "silent"},
            {"name": "c", "state": "needs_config"}]
    assert mod.failing(rows) == []
    rows.append({"name": "d", "state": "stale", "expected_stale": None})
    assert [r["name"] for r in mod.failing(rows)] == ["d"]
    rows.append({"name": "e", "state": "error"})
    assert [r["name"] for r in mod.failing(rows)] == ["d", "e"]
