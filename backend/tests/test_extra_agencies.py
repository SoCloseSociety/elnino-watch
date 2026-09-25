"""extra_agencies collectors against REAL payloads captured 2026-09-24 (no network)."""

from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import extra_agencies as A
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "extra_nasa" / "agencies"


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


def latest(source: str, series: str) -> dict:
    rows = db.query("SELECT ts, value, meta FROM observations WHERE source=? AND series=? "
                    "ORDER BY ts DESC LIMIT 1", (source, series))
    assert rows, f"no {series}"
    return rows[0]


# ----------------------------------------------------------------- sea level


def test_sla_nino34_area_mean_in_cm():
    rows = A.parse_sla_csv(fx("sla_nino34.csv").decode(), "nino34")
    by = {r["ts"]: r for r in rows}
    assert set(by) == {"2026-09-20", "2026-09-21", "2026-09-22"}
    assert by["2026-09-22"]["value"] == 37.26
    assert by["2026-09-22"]["meta"]["cells"] == 500


def test_sla_url_uses_erddap_index_and_stride():
    assert A.sla_url("samui", 3) == (
        A.SLA_DATASET + ".csv?sla[last-2:last][(9.125):1:(10.375)][(99.875):1:(100.625)]")


@respx.mock
async def test_sla_collector_regions_and_gradient():
    files = {"nino34": "sla_nino34.csv", "west_pacific": "sla_west_pacific.csv",
             "samui": "sla_samui.csv"}

    def answer(request):
        url = str(request.url).replace("%5B", "[").replace("%5D", "]").replace("%28", "(") \
            .replace("%29", ")")
        for region, f in files.items():
            if url == A.sla_url(region):
                return httpx.Response(200, content=fx(f))
        return httpx.Response(404, text="Error { code=404; message=\"Not Found\" }")
    respx.get(url__startswith=A.SLA_DATASET).mock(side_effect=answer)
    await run(A.NoaaSlaRegions())
    grad = latest("noaa_sla_regions", "sla_pacific_east_minus_west")
    assert grad["ts"] == "2026-09-22"
    assert grad["value"] == round(37.26 - latest("noaa_sla_regions", "sla_west_pacific")["value"],
                                  2)
    assert latest("noaa_sla_regions", "sla_samui_coast")["value"] == 6.11
    notes = db.query("SELECT detail FROM source_runs WHERE source='noaa_sla_regions'")[0]
    assert notes["detail"]["regions"]["nino12"].startswith("error: HTTPStatusError")


@respx.mock
async def test_sla_server_down_stops_early():
    route = respx.get(url__startswith=A.SLA_DATASET).mock(
        return_value=httpx.Response(502, text="Proxy Error"))
    async with httpx.AsyncClient() as c:
        res = await run_collector(A.NoaaSlaRegions(), c)
    assert not res["ok"] and route.call_count == 1


def test_sla_bad_header():
    with pytest.raises(SourceChanged):
        A.parse_sla_csv("time,lat,lon,x\nUTC,deg,deg,m\n", "nino34")


# ----------------------------------------------------------------- Climate Pulse


@respx.mock
async def test_climate_pulse():
    respx.get(A.PULSE_2T_URL).mock(return_value=httpx.Response(200, content=fx("pulse_2t.csv")))
    respx.get(A.PULSE_SST_URL).mock(return_value=httpx.Response(200, content=fx("pulse_sst.csv")))
    await run(A.C3sClimatePulse())
    t = latest("c3s_climate_pulse", "era5_global_t2m_anom")
    assert t["ts"] == "2026-09-22" and t["value"] == 0.776
    assert t["meta"]["status"] == "preliminary"
    s = latest("c3s_climate_pulse", "era5_sst_6060")
    assert s["value"] == 21.034 and s["meta"]["status"] == "final"


# ----------------------------------------------------------------- NCEI


@respx.mock
async def test_ncei_cag():
    respx.get(A.cag_url(*A.CAG_GLOBAL)).mock(
        return_value=httpx.Response(200, content=fx("cag_globe_land_ocean.csv")))
    respx.get(A.cag_url(*A.CAG_ASIA)).mock(
        return_value=httpx.Response(200, content=fx("cag_asia_land.csv")))
    await run(A.NceiClimateAtAGlance())
    g = latest("ncei_cag", "ncei_global_anom")
    assert g == {"ts": "2026-08-15", "value": 1.32, "meta": {"baseline": "1901-2000"}}
    assert latest("ncei_cag", "ncei_asia_land_anom")["value"] == 1.75


def test_cag_url_ends_this_year():
    assert A.cag_url("globe/land_ocean", 1850, 2026).endswith("/1/0/1850-2026/data.csv")


@respx.mock
async def test_ncei_monthly_report():
    respx.get(A.NCEI_RSS_URL).mock(return_value=httpx.Response(
        200, content=fx("ncei_monthly_report.rss")))
    await run(A.NceiMonthlyReport())
    rows = db.query("SELECT title, kind, published_at FROM feed_items ORDER BY title")
    assert [r["title"] for r in rows] == [
        "August 2026 Global Drought Narrative", "August 2026 Monthly Global Climate Report",
        "August 2026 Monthly Tropical Cyclones Report"]
    assert rows[0]["kind"] == "official" and rows[0]["published_at"] == "2026-09-10T15:00:00+00:00"


# ----------------------------------------------------------------- Met Office


@respx.mock
async def test_hadobs():
    respx.get(A.HADCRUT_URL).mock(return_value=httpx.Response(
        200, content=fx("hadcrut5_global_monthly.csv")))
    respx.get(A.HADSST_GLOBE_URL).mock(return_value=httpx.Response(
        200, content=fx("hadsst4_globe_monthly.csv")))
    respx.get(A.HADSST_TROP_URL).mock(return_value=httpx.Response(
        200, content=fx("hadsst4_trop_monthly.csv")))
    await run(A.MetOfficeHadObs())
    h = latest("metoffice_hadobs", "hadcrut5_global_anom")
    assert h["ts"] == "2026-07-15" and h["value"] == 1.097
    assert h["meta"]["ci95"] == [1.039, 1.154]
    assert latest("metoffice_hadobs", "hadsst4_global_anom")["value"] == 1.139
    assert latest("metoffice_hadobs", "hadsst4_tropics_anom")["value"] == 1.105


def test_hadcrut_changed_columns():
    with pytest.raises(SourceChanged):
        A.parse_hadcrut("Date,Value\n2026-01,1.0\n")


# ----------------------------------------------------------------- ECMWF


@respx.mock
async def test_ecmwf_seas5_asia():
    def answer(request):
        p = request.url.params
        if p.get("base_time") == A.EcmwfSeas5Asia.probe_time:
            return httpx.Response(404, content=fx("ecmwf_rain_base_times.json"))
        if p.get("valid_time") == A.EcmwfSeas5Asia.probe_time:
            return httpx.Response(404, content=fx("ecmwf_rain_valid_times.json"))
        if "2mtm" in request.url.path:
            return httpx.Response(200, content=fx("ecmwf_asia_t2m.json"))
        return httpx.Response(200, content=fx("ecmwf_asia_rain.json"))
    respx.get(url__startswith=A.ECMWF_API).mock(side_effect=answer)
    respx.get(url__startswith="https://charts.ecmwf.int/content/").mock(
        return_value=httpx.Response(200, content=(FIX.parent / "nasa" / "gibs_flood_tile.png")
                                    .read_bytes(), headers={"content-type": "image/png"}))
    await run(A.EcmwfSeas5Asia())
    st = db.get_status("ecmwf_seas5_asia")["value"]
    assert st["base_time"] == "2026-09-01T00:00:00Z"
    assert [c["season"] for c in st["charts"]] == ["OND 2026", "NDJ 2026", "DJF 2026",
                                                   "JFM 2027", "OND 2026", "NDJ 2026"]
    assert [c["kind"] for c in st["charts"]] == ["asia_rain"] * 4 + ["asia_t2m"] * 2
    assert st["charts"][0]["url"].startswith("https://charts.ecmwf.int/content/")
    item = db.query("SELECT ext_id, published_at FROM feed_items WHERE source='ecmwf_seas5_asia'")
    assert item == [{"ext_id": "2026-09-01", "published_at": "2026-09-01"}]


def test_ecmwf_available_times():
    import json
    times = A.parse_base_times(json.loads(fx("ecmwf_rain_base_times.json")))
    assert times[0] == "2026-09-01T00:00:00Z" and times[1] == "2026-08-01T00:00:00Z"
    assert A.parse_valid_times(json.loads(fx("ecmwf_rain_valid_times.json")))[-1] == \
        "2027-01-02T00:00:00Z"
    assert A.season_label("2027-01-02T00:00:00Z") == "JFM 2027"
