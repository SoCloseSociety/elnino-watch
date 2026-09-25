"""Maritime collectors against REAL payloads captured 2026-09-24 (no network).

Fixtures: tao_*.json are real data.php responses with each sensor's `obs` trimmed to
its 13 most recent readings; crw_*.txt keep the real header + the last 400 daily rows.
"""

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import maritime as M
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "maritime"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


async def run(col) -> dict:
    async with httpx.AsyncClient() as c:
        res = await run_collector(col, c)
    assert res["ok"], res
    return res


def series(source: str, name: str) -> list[dict]:
    return db.query("SELECT ts, value, unit, meta FROM observations WHERE source=? AND series=? "
                    "ORDER BY ts", (source, name))


# --------------------------------------------------------------------------- TAO

def test_active_stations_keeps_only_tao():
    st = M.parse_active_tao(fx("activestations_subset.xml").decode())
    assert [s["id"] for s in st] == ["32303", "32304", "51311"]
    assert st[0] == {"id": "32303", "name": "5N 95W", "lat": 5.0, "lon": -95.0}


def test_tao_station_parse():
    import json
    r = M.parse_tao_station(json.loads(fx("tao_32303.json")))
    assert r["sst"] == 29.064 and r["sst_depth"] == 1
    assert r["air_temp"] == 28.162 and r["wind"] == 2.8
    assert r["observed_at"] == "2026-09-24T12:10:00+00:00"
    assert r["sst_hourly"] == [("2026-09-24T11:00:00+00:00", 29.101),
                               ("2026-09-24T12:00:00+00:00", 29.063)]


def test_tao_bad_payload_is_source_changed():
    with pytest.raises(SourceChanged):
        M.parse_tao_station({"station": {}})


@respx.mock
async def test_tao_collector_end_to_end():
    respx.get(M.NDBC_ACTIVE_URL).mock(
        return_value=httpx.Response(200, content=fx("activestations_subset.xml")))

    def data(request):
        sid = request.url.params["station"]
        return httpx.Response(200, content=fx(f"tao_{sid}.json"),
                              headers={"content-type": "application/json"})

    respx.get(M.TAO_DATA_URL).mock(side_effect=data)
    res = await run(M.TaoBuoys())
    assert res["items"] == 4  # 2 hourly SST points x 2 buoys with a surface sensor
    st = db.get_status("tao_buoys")["value"]
    assert [s["id"] for s in st] == ["32303", "32304", "51311"]
    b = {s["id"]: s for s in st}
    assert b["32303"]["sst"] == 29.064 and b["32303"]["lat"] == 5.0
    assert b["32303"]["url"] == "https://tao.ndbc.noaa.gov/station.php?station=32303"
    assert b["32304"]["sst"] is None  # buoy lists no sensors right now: shown, not invented
    assert b["51311"]["sst"] == 30.163 and b["51311"]["wind"] is None
    pts = series("tao_buoys", "tao_51311_sst")
    assert [p["value"] for p in pts] == [30.192, 30.163]
    assert pts[0]["unit"] == "degC" and pts[0]["meta"]["depth_m"] == 1
    run_row = db.query("SELECT detail FROM source_runs WHERE source='tao_buoys'")[0]
    assert run_row["detail"]["no_sst"] == ["32304"]


@respx.mock
async def test_tao_all_stations_failing_is_an_error():
    respx.get(M.NDBC_ACTIVE_URL).mock(
        return_value=httpx.Response(200, content=fx("activestations_subset.xml")))
    respx.get(M.TAO_DATA_URL).mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as c:
        res = await run_collector(M.TaoBuoys(), c)
    assert not res["ok"]


# --------------------------------------------------------------------------- CRW

def test_crw_parse():
    vs = M.parse_crw_vs(fx("crw_west_gulf_of_thailand.txt").decode())
    assert vs["name"] == "Western Gulf of Thailand"
    assert (vs["lat"], vs["lon"], vs["mmm"]) == (10.9, 99.75, 30.1316)
    assert vs["rows"][-1] == {"date": "2026-09-22", "sst": 29.69, "ssta": 0.7243,
                              "dhw": 0.0, "alert": 1}


def test_crw_changed_columns():
    with pytest.raises(SourceChanged):
        M.parse_crw_vs("Name:\nX\n \nYYYY MM DD SST\n2026 01 01 29.0\n")


@respx.mock
async def test_crw_collector_partial_failure_keeps_others():
    for st in ("west_gulf_of_thailand", "east_gulf_of_thailand"):
        respx.get(M.CRW_VS_URL.format(station=st)).mock(
            return_value=httpx.Response(200, content=fx(f"crw_{st}.txt")))
    respx.get(M.CRW_VS_URL.format(station="southwestern_thailand")).mock(
        return_value=httpx.Response(503))
    res = await run(M.CoralReefWatch())
    assert res["items"] > 0
    st = {s["station"]: s for s in db.get_status("crw_bleaching")["value"]}
    assert set(st) == {"west_gulf_of_thailand", "east_gulf_of_thailand"}
    w = st["west_gulf_of_thailand"]
    assert (w["date"], w["sst"], w["dhw"], w["alert"]) == ("2026-09-22", 29.69, 0.0, 1)
    assert w["alert_label"] == "Bleaching Watch"
    last = series("crw_vs", "crw_west_gulf_of_thailand_dhw")[-1]
    assert (last["ts"], last["value"]) == ("2026-09-22", 0.0)
    ev = db.query("SELECT * FROM events WHERE source='crw_vs'")
    assert len(ev) == 1 and ev[0]["category"] == "bleaching" and ev[0]["severity"] == "info"
    detail = db.query("SELECT detail FROM source_runs WHERE source='crw_vs'")[0]["detail"]
    assert "southwestern_thailand" in detail["failed"]


# --------------------------------------------------------------------------- Open-Meteo Marine

def test_marine_parse_daily():
    import json
    res = M.parse_marine(json.loads(fx("openmeteo_marine_samui.json")), today=date(2026, 9, 24))
    today = {r["series"]: r for r in res["rows"] if r["ts"] == "2026-09-24"}
    assert today["samui_wave_height"]["value"] == 0.46
    assert today["samui_sst"]["value"] == 30.11
    assert today["samui_swell_height"]["value"] == 0.26
    assert today["samui_sst"]["meta"]["forecast"] is False
    fut = [r for r in res["rows"] if r["ts"] > "2026-09-24"]
    assert fut and all(r["meta"]["forecast"] for r in fut)
    assert res["grid"] == [9.541664, 100.125015]


@respx.mock
async def test_marine_collector():
    respx.get(M.MARINE_URL).mock(
        return_value=httpx.Response(200, content=fx("openmeteo_marine_samui.json")))
    res = await run(M.OpenMeteoMarine())
    assert res["items"] == 42  # 14 days x 3 series
    st = db.get_status("samui_marine")["value"]
    assert st["grid"] == [9.541664, 100.125015]


def test_marine_missing_blocks():
    with pytest.raises(SourceChanged):
        M.parse_marine({"hourly": {"time": []}})
