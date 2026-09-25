"""Exit plan: signals, 7-day departure windows, routes, recommendation (synthetic DB inputs)."""

from __future__ import annotations

import os

os.environ.setdefault("SCHEDULER", "false")

from datetime import timedelta
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app import db
from app.local import exit as ex
from app.local import risk
from app.local.collectors import today_bkk


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def ok_run(source: str) -> None:
    db.record_run(source, db.now_iso(), ok=True, items=1)


def series(source: str, name: str, values: list[float]) -> None:
    t = today_bkk()
    db.upsert_observations(source, [
        {"series": name, "ts": (t + timedelta(days=i)).isoformat(), "value": v}
        for i, v in enumerate(values)])


def test_empty_db_everything_unknown():
    p = ex.exit_plan()
    assert {s["status"] for s in p["signals"]} == {"unknown"}
    assert len(p["windows"]) == 7
    assert all(not w["ok"] and w["status"] == "unknown" for w in p["windows"])
    assert "cannot be assessed" in p["recommendation"]
    assert p["windows"][0]["date"] == today_bkk().isoformat()


def test_windows_follow_waves_gusts_and_tmd():
    series("openmeteo_marine", "samui_wave_height", [0.8, 2.2, 3.4, 1.0, 1.0, 1.0, 1.0])
    series("openmeteo_samui", "samui_wind_gust_max", [30, 55, 40, 80, 30, 30, 30])
    ok_run("openmeteo_marine")
    ok_run("openmeteo_samui")
    ok_run("gdacs")
    st = [w["status"] for w in ex.windows(today_bkk(), ex.cyclone_signal())]
    assert st == ["ok", "caution", "blocked", "blocked", "ok", "ok", "ok"]
    db.set_status("tmd_warnings", {"items": [{
        "issue": "9/2569", "until": (today_bkk() + timedelta(days=1)).isoformat(),
        "affects_samui": True, "strong_waves": True, "strong_waves_gulf": True,
        "small_boats_ashore": True}]})
    ok_run("tmd_warnings")
    wins = ex.windows(today_bkk(), ex.cyclone_signal())
    assert [w["status"] for w in wins][:2] == ["blocked", "blocked"]
    assert "small boats ashore" in wins[0]["reason"]
    assert ex.tmd_sea_signal()["status"] == "blocked"


def test_cyclone_signal_and_first_three_days():
    series("openmeteo_marine", "samui_wave_height", [0.5] * 7)
    ok_run("openmeteo_marine")
    db.upsert_events("gdacs", [{"ext_id": "TC9", "category": "cyclone", "title": "TC NEAR",
                                "severity": "orange", "lat": 13.5, "lon": 103.0}])
    ok_run("gdacs")
    cyc = ex.cyclone_signal()
    assert cyc["status"] == "blocked" and 400 < cyc["value"] < 800
    st = [w["status"] for w in ex.windows(today_bkk(), cyc)]
    assert st[:3] == ["blocked"] * 3 and st[3] == "ok"


def test_signal_thresholds():
    series("openmeteo_marine", "samui_wave_height", [1.9, 2.0])
    series("openmeteo_samui", "samui_wind_gust_max", [61, 62])
    series("openmeteo_samui", "samui_precip", [95, 10])
    ok_run("openmeteo_marine")
    ok_run("openmeteo_samui")
    t = today_bkk()
    assert ex.sea_signal(t)["status"] == "caution" and ex.sea_signal(t)["value"] == 2.0
    assert ex.gust_signal(t)["status"] == "caution"
    assert ex.rain_signal(t)["status"] == "caution"


def test_recommendation_by_level():
    wins = [{"date": "2026-10-01", "ok": True}]
    closed = [{"id": "waves", "status": "blocked"}]
    assert ex.recommendation({"level": 4}, closed, wins).startswith(
        "LEAVE is advised but the sea route looks closed")
    assert ex.recommendation({"level": 4}, [{"id": "waves", "status": "ok"}],
                             wins).startswith("LEAVE the island")
    assert ex.recommendation({"level": 1}, [], wins).startswith("No reason to leave")
    assert "at least 'prepare'" in ex.recommendation({"level": None, "level_floor": 2}, [],
                                                     [])


def test_routes_are_verified_official_https_urls():
    ids = [r["id"] for r in ex.ROUTES]
    assert len(ids) == len(set(ids))
    assert {r["mode"] for r in ex.ROUTES} == {"ferry", "air", "rail"}
    hosts = {urlparse(r["url"]).hostname for r in ex.ROUTES}
    assert hosts == {"www.seatranferry.com", "www.rajaferryport.com", "www.lomprayah.com",
                     "www.samuiairport.com", "www.thaiairways.com",
                     "minisite.airports.go.th", "www.railway.co.th"}
    for r in ex.ROUTES:
        assert r["url"].startswith("https://") and r["notes"]
        assert "THB" not in r["notes"] and ":00" not in r["notes"]  # no fares / times
    assert all(c["priority"] in ("must", "should", "nice") for c in ex.CHECKLIST)
    assert {"home_water", "home_power", "home_windows", "home_high", "pets", "docs",
            "money", "booking"} <= {c["id"] for c in ex.CHECKLIST}


def test_api_exit_and_leave_scenario():
    from app.main import app

    c = TestClient(app)
    body = c.get("/api/local/exit").json()
    assert {"recommendation", "signals", "routes", "checklist", "windows"} <= set(body)
    for s in body["signals"]:
        assert {"id", "label", "status", "value", "source", "url", "observed_at"} <= set(s)
    assert body["level_key"] == risk.evaluate(save=False)["level_key"] == "unknown"
    prep = c.get("/api/preparedness").json()
    leave = next(s for s in prep["scenarios"] if s["id"] == "leave")
    assert leave["exit_plan"] == "/api/local/exit"
