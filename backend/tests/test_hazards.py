"""Hazard collectors against REAL payloads captured 2026-09-24 (no network).

GDACS / EONET fixtures are real responses reduced to a subset of their features;
the FIRMS CSV keeps the real header + first 300 detections; thaiwater_dam_load.json
keeps only the real `dam_data` block of analyst/dam_load.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import hazards as H
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "hazards"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def js(name: str):
    return json.loads(fx(name))


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


async def run(col) -> dict:
    async with httpx.AsyncClient() as c:
        res = await run_collector(col, c)
    assert res["ok"], res
    return res


def events(source: str) -> dict[str, dict]:
    return {e["ext_id"]: e for e in db.query("SELECT * FROM events WHERE source=?", (source,))}


# --------------------------------------------------------------------------- GDACS

def test_gdacs_parse_cyclone_keeps_track_url():
    ev = {e["ext_id"]: e for e in H.parse_gdacs(js("gdacs_events4app.json"))}
    tc = ev["TC_1001326"]
    assert tc["category"] == "cyclone" and tc["severity"] == "orange"
    assert (tc["lat"], tc["lon"]) == (18.1, 83.7)
    assert tc["payload"]["country"] == "India"
    assert tc["payload"]["geometry_url"].startswith(
        "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=TC&eventid=1001326")
    assert tc["url"].startswith("https://www.gdacs.org/report.aspx?eventid=1001326")
    assert tc["started_at"] == "2026-09-22T18:00:00+00:00"


def test_gdacs_search_drops_closed_events():
    raw = js("gdacs_search_tcflvo.json")["features"]
    parsed = H.parse_gdacs(js("gdacs_search_tcflvo.json"))
    assert len(parsed) == 8 < len(raw)


def test_gdacs_no_features_is_source_changed():
    with pytest.raises(SourceChanged):
        H.parse_gdacs({"type": "FeatureCollection"})


@respx.mock
async def test_gdacs_collector_merges_app_and_search():
    respx.get(H.GDACS_APP_URL).mock(
        return_value=httpx.Response(200, content=fx("gdacs_events4app.json")))

    def search(request):
        name = ("gdacs_search_dr.json" if request.url.params["eventlist"] == "DR"
                else "gdacs_search_tcflvo.json")
        return httpx.Response(200, content=fx(name))

    respx.get(H.GDACS_SEARCH_URL).mock(side_effect=search)
    # a stale event from a previous run must disappear (replace_events)
    db.upsert_events("gdacs", [{"ext_id": "TC_1", "category": "cyclone", "lat": 0, "lon": 0}])
    res = await run(H.GdacsEvents())
    ev = events("gdacs")
    assert "TC_1" not in ev
    assert res["items"] == len(ev) == 16  # 15 from EVENTS4APP + the Brazil drought
    assert ev["DR_1015915"]["category"] == "drought"
    assert ev["DR_1015915"]["title"] == "Drought in Brazil"
    cats = {e["category"] for e in ev.values()}
    assert {"cyclone", "flood", "earthquake", "wildfire", "drought"} <= cats


# --------------------------------------------------------------------------- EONET

def test_eonet_parse():
    ev = {e["ext_id"]: e for e in H.parse_eonet(js("eonet_open.json"))}
    assert len(ev) == 6  # the seaLakeIce event is skipped
    tc = ev["EONET_24785"]
    assert tc["category"] == "cyclone" and tc["title"] == "Tropical Cyclone 01B"
    assert tc["geometry"]["type"] == "LineString"
    assert (tc["lat"], tc["lon"]) == (18.1, 83.7)  # latest fix, not the first one
    assert tc["updated_at"] == "2026-09-24T00:00:00+00:00"
    assert tc["payload"]["magnitude_unit"] == "kts"
    assert ev["EONET_24710"]["category"] == "wildfire"
    assert ev["EONET_24710"]["geometry"]["type"] == "Point"


@respx.mock
async def test_eonet_collector():
    respx.get(H.EONET_URL).mock(return_value=httpx.Response(200, content=fx("eonet_open.json")))
    res = await run(H.EonetEvents())
    assert res["items"] == 6


# --------------------------------------------------------------------------- FIRMS

def test_firms_clusters():
    cl = H.parse_firms_csv(fx("firms_viirs_snpp_sea_24h.csv").decode(), "SouthEast_Asia")
    assert len(cl) == 22
    top = max(cl, key=lambda c: c["payload"]["detections"])
    assert top["ext_id"] == "-11.0_142.5"
    assert top["payload"]["detections"] == 39 and top["severity"] == "orange"
    assert all(c["payload"]["detections"] >= 3 for c in cl)


def test_firms_changed_columns():
    with pytest.raises(SourceChanged):
        H.parse_firms_csv("lat,lon\n1,2\n", "x")


@respx.mock
async def test_firms_collector_dedupes_overlapping_regions():
    csv_body = fx("firms_viirs_snpp_sea_24h.csv")
    for region in H.FIRMS_REGIONS:  # same real file for every region -> same cells
        respx.get(H.FIRMS_REGION_URL.format(region=region)).mock(
            return_value=httpx.Response(200, content=csv_body))
    res = await run(H.FirmsFires())
    assert res["items"] == 22


# --------------------------------------------------------------------------- TMD (English)

def test_tmd_en_parse():
    items = H.parse_tmd_warnings_en(fx("tmd_warning_storm_en.html").decode())
    assert len(items) == 10
    top = items[0]
    assert top["ext_id"] == "223/2026" and top["published_at"] == "2026-09-24"
    assert top["title"] == "Heavy to Very Heavy Rain in Thailand No.7 (223/2026)"
    assert top["url"].startswith("https://www.tmd.go.th/en/warning-and-events/warning-storm/")
    assert "low-pressure cell over Cambodia" in top["summary"]
    assert top["kind"] == "official" and top["lang"] == "en" and "thailand" in top["tags"]
    assert items[3]["title"] == "Heavy to Very Heavy Rain in Thailand No.4 (220/2026)"


def test_tmd_en_markup_change():
    with pytest.raises(SourceChanged):
        H.parse_tmd_warnings_en("<html><body>maintenance</body></html>")


@respx.mock
async def test_tmd_en_collector():
    respx.get(H.TMD_WARN_EN_URL).mock(
        return_value=httpx.Response(200, content=fx("tmd_warning_storm_en.html")))
    res = await run(H.TmdWarningsEn())
    assert res["items"] == 10


# --------------------------------------------------------------------------- ASMC

def test_asmc_alerts_parse():
    a = H.parse_asmc_alerts(fx("asmc_alerts.html").decode())
    assert a[0]["issued"] == "2026-08-26" and a[0]["level"] == 3
    assert a[0]["subregion"] == "southern"
    assert a[0]["title"] == "Activation of Alert Level 3 for the Southern ASEAN Region"
    assert "Kalimantan" in a[0]["text"]
    mekong = next(x for x in a if x["subregion"] == "mekong")
    assert (mekong["issued"], mekong["level"]) == ("2026-05-14", 0)


@respx.mock
async def test_asmc_alerts_collector():
    respx.get(H.ASMC_ALERTS_URL).mock(
        return_value=httpx.Response(200, content=fx("asmc_alerts.html")))
    await run(H.AsmcHazeAlerts())
    st = db.get_status("asmc_haze_alert")["value"]
    assert st["southern"]["level"] == 3 and st["southern"]["issued"] == "2026-08-26"
    assert st["mekong"]["level"] == 0
    feed = db.query("SELECT * FROM feed_items WHERE source='asmc_haze_alerts'")
    assert len(feed) == 20 and all(f["kind"] == "official" for f in feed)


@respx.mock
async def test_asmc_hotspots_collector():
    def post(request):
        body = request.content.decode()
        name = ("asmc_hotspots_mainland.json" if "Thailand" in body
                else "asmc_hotspots_maritime.json")
        return httpx.Response(200, content=fx(name))

    respx.post(H.ASMC_HOTSPOT_URL).mock(side_effect=post)
    res = await run(H.AsmcHotspots())
    assert res["items"] == 140  # 14 days x 10 regions
    kal = db.query("SELECT ts, value FROM observations WHERE series='asmc_hotspots_kalimantan' "
                   "ORDER BY ts DESC LIMIT 1")[0]
    assert (kal["ts"], kal["value"]) == ("2026-09-23", 792)


# --------------------------------------------------------------------------- ThaiWater dams

def test_thai_dams_parse():
    d = H.parse_thai_dams(js("thaiwater_dam_load.json"))
    assert d["date"] == "2026-09-24" and d["total_dams"] == 35
    assert d["total_storage_pct"] == 75.36
    assert d["dams"][0]["name"] == "Kra Siew" and d["dams"][0]["storage_pct"] == 22.74
    rp = next(x for x in d["dams"] if x["slug"] == "ratchaprapa")
    assert rp["storage_pct"] == 72.84 and rp["province"] == "Surat Thani"


@respx.mock
async def test_thai_dams_collector():
    respx.get(H.THAIWATER_DAM_URL).mock(
        return_value=httpx.Response(200, content=fx("thaiwater_dam_load.json")))
    res = await run(H.ThaiDamsNational())
    assert res["items"] == 36  # 35 dams + the national total
    tot = db.query("SELECT value FROM observations WHERE series='thai_large_dams_storage_pct'")
    assert tot[0]["value"] == 75.36
    assert db.get_status("thai_dams")["value"]["total_storage_pct"] == 75.36
