"""extra_hazards collectors against REAL payloads captured 2026-09-24 (no network)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import extra_hazards as H
from app.collectors.base import SourceChanged, run_collector
from app.config import settings

FIX = Path(__file__).parent / "fixtures" / "extra"
JTWC = "https://www.metoc.navy.mil/jtwc/products/"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


async def run(col) -> dict:
    async with httpx.AsyncClient() as c:
        return await run_collector(col, c)


def events(source: str) -> dict[str, dict]:
    return {e["ext_id"]: e for e in db.query("SELECT * FROM events WHERE source=?", (source,))}


@respx.mock
async def test_jma_typhoon_track_and_distance():
    respx.get(H.JMA_TARGET_URL).mock(return_value=httpx.Response(200, content=fx(
        "jma_targetTc.json")))
    respx.get(H.JMA_TC_BASE + "TC2632/forecast.json").mock(
        return_value=httpx.Response(200, content=fx("jma_TC2632_forecast.json")))
    respx.get(H.JMA_TC_BASE + "TC2632/specifications.json").mock(
        return_value=httpx.Response(200, content=fx("jma_TC2632_specifications.json")))
    res = await run(H.JmaTyphoons())
    assert res["ok"], res
    ev = events("jma_typhoons")["TC2632"]
    assert ev["title"] == "Tropical Storm Surigae (JMA 2626)"
    assert ev["category"] == "cyclone" and ev["severity"] == "green"  # > 3000 km away
    assert (ev["lat"], ev["lon"]) == (19.2, 132.0)
    assert ev["updated_at"] == "2026-09-24T12:45:00+00:00"
    p = ev["payload"]
    assert p["wind_kt"] == 40 and p["pressure_hpa"] == 1002
    assert [f["hours"] for f in p["forecast"]] == [0, 12, 24, 48, 72, 96, 120]
    assert p["forecast"][3]["class"] == "TY" and p["forecast"][3]["wind_kt"] == 75
    assert 3000 < p["closest_km"] < 3300
    assert ev["geometry"]["type"] == "LineString"
    assert ev["geometry"]["coordinates"][0] == [140.7, 14.3]  # [lon, lat]


@respx.mock
async def test_jma_no_storm_clears_map():
    db.upsert_events("jma_typhoons", [{"ext_id": "TC2600", "category": "cyclone", "lat": 1,
                                       "lon": 1}])
    respx.get(H.JMA_TARGET_URL).mock(return_value=httpx.Response(200, json=[]))
    res = await run(H.JmaTyphoons())
    assert res["ok"] and res["items"] == 0
    assert events("jma_typhoons") == {}


def test_severity_by_distance():
    assert H.track_severity(120) == "red"
    assert H.track_severity(650) == "orange"
    assert H.track_severity(2000) == "green"
    assert H.home_km(settings.home_lat, settings.home_lon) == 0


@respx.mock
async def test_jtwc_warnings_and_advisory():
    respx.get(H.JTWC_RSS).mock(return_value=httpx.Response(200, content=fx("jtwc.rss")))
    respx.get(JTWC + "wp2526web.txt").mock(
        return_value=httpx.Response(200, content=fx("jtwc_wp2526web.txt")))
    respx.get(JTWC + "io0126web.txt").mock(
        return_value=httpx.Response(200, content=fx("jtwc_io0126web.txt")))
    respx.get(JTWC + "abpwweb.txt").mock(
        return_value=httpx.Response(200, content=fx("jtwc_abpwweb.txt")))
    res = await run(H.JtwcWarnings())
    assert res["ok"], res
    ev = events("jtwc_warnings")
    assert set(ev) == {"wp2526", "io0126"}  # east Pacific storms are not in our basins
    wp = ev["wp2526"]
    assert wp["title"] == "Tropical Storm 25W (Surigae) (JTWC warning 5)"
    assert (wp["lat"], wp["lon"]) == (18.9, 133.1)
    assert wp["updated_at"] == "2026-09-24T06:00:00+00:00"
    assert wp["payload"]["wind_kt"] == 45 and wp["payload"]["gust_kt"] == 55
    assert wp["payload"]["forecast"][-1]["wind_kt"] is not None
    io = ev["io0126"]
    assert io["payload"]["final"] is True and io["severity"] == "green"
    assert (io["lat"], io["lon"]) == (18.1, 83.7)
    feed = db.query("SELECT * FROM feed_items WHERE source='jtwc_warnings'")
    assert len(feed) == 1 and feed[0]["ext_id"] == "abpw-240600"
    assert feed[0]["published_at"] == "2026-09-24T06:00:00+00:00"
    assert "MALAY PENINSULA" in feed[0]["summary"]


def test_jtwc_dtg_month_rollover():
    ref = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
    assert H._dtg("301800", ref) == datetime(2026, 9, 30, 18, 0, tzinfo=UTC)
    assert H._dtg("010000", ref) == datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def test_jtwc_garbage_warning_is_source_changed():
    with pytest.raises(SourceChanged):
        H.parse_jtwc_warning("NOTHING HERE", "wp9999", datetime.now(UTC))


@respx.mock
async def test_usgs_regional_quakes():
    respx.get(H.USGS_URL).mock(return_value=httpx.Response(200, content=fx(
        "usgs_4.5_week.geojson")))
    res = await run(H.UsgsQuakesRegion())
    assert res["ok"], res
    ev = events("usgs_quakes_region")
    assert len(ev) == 13  # of 102 worldwide, within 3000 km of Koh Samui
    assert all(e["payload"]["distance_km"] <= 3000 for e in ev.values())
    assert all(e["category"] == "earthquake" for e in ev.values())
    total = len(json.loads(fx("usgs_4.5_week.geojson"))["features"])
    assert total == 102


@respx.mock
async def test_ptwc_message():
    respx.get(H.PTWC_URL).mock(return_value=httpx.Response(200, content=fx("ptwc_pheb.xml")))
    res = await run(H.PtwcTsunami())
    assert res["ok"], res
    it = db.query("SELECT * FROM feed_items WHERE source='ptwc_tsunami'")[0]
    assert it["kind"] == "official"
    assert it["title"] == ("PTWC Tsunami Information Statement Number 1 -- "
                           "Vicinity Of Puerto Rico")
    assert it["published_at"] == "2026-09-18T13:25:30+00:00"
    assert (it["lat"], it["lon"]) == (17.949, -66.937)
    assert it["url"].endswith("WECA42.txt")


async def test_reliefweb_needs_config(monkeypatch):
    monkeypatch.delenv("RELIEFWEB_APPNAME", raising=False)
    res = await run(H.ReliefWebReports())
    assert not res["ok"] and res["needs_config"]
    row = db.query("SELECT error FROM source_runs WHERE source='reliefweb_reports'")[0]
    assert row["error"].startswith("needs_config")
