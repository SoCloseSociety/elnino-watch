"""extra_nasa collectors against REAL payloads captured 2026-09-24 (no network)."""

import re
from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import extra_nasa as N
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "extra_nasa" / "nasa"


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


# ----------------------------------------------------------------- POWER


def test_power_daily_skips_fill_values():
    rows = N.parse_power_daily(__import__("json").loads(fx("power_daily.json")))
    t2m = {r["ts"]: r["value"] for r in rows if r["series"] == "samui_power_t2m"}
    assert t2m["2026-09-21"] == 28.56
    assert "2026-09-22" not in t2m  # -999 in the payload
    solar = [r for r in rows if r["series"] == "samui_power_solar"]
    assert max(r["ts"] for r in solar) < "2026-09-20"  # solar lags more


@respx.mock
async def test_power_collector_with_climatology_and_crosscheck():
    respx.get(url__startswith=N.POWER_DAILY_URL).mock(
        return_value=httpx.Response(200, content=fx("power_daily.json")))
    respx.get(url__startswith=N.POWER_CLIM_URL).mock(
        return_value=httpx.Response(200, content=fx("power_climatology.json")))
    # an ERA5 value from the Open-Meteo collector for the same day, to cross-check against
    db.upsert_observations("openmeteo_samui_era5", [
        {"series": "samui_era5_temp_max", "ts": "2026-09-21", "value": 30.28, "unit": "degC"}])
    await run(N.NasaPowerSamui())
    a = latest("nasa_power_samui", "samui_power_t2m_anom")
    assert a["ts"] == "2026-09-21" and a["value"] == round(28.56 - 27.9, 2)  # SEP normal 27.9
    st = db.get_status("samui_power")["value"]
    assert st["last_day"] == "2026-09-21" and st["window_days"] == 30
    assert st["climatology"]["months"]["PRECTOTCORR"]["NOV"] == 12.5
    cc = db.get_status("samui_power_crosscheck")["value"]["pairs"]["samui_power_t2m_max"]
    assert cc == {"compared_with": "samui_era5_temp_max", "days": 1, "mean_diff": -1.0,
                  "mean_abs_diff": 1.0}


def test_power_changed_format():
    with pytest.raises(SourceChanged):
        N.parse_power_daily({"properties": {"parameter": {"T2M": {}}}})


# ----------------------------------------------------------------- GISTEMP


@respx.mock
async def test_gistemp():
    respx.get(N.GISTEMP_URL).mock(return_value=httpx.Response(200, content=fx("GLB.Ts+dSST.csv")))
    respx.get(N.GISTEMP_ZON_URL).mock(
        return_value=httpx.Response(200, content=fx("ZonAnn.Ts+dSST.csv")))
    await run(N.NasaGistemp())
    g = latest("nasa_gistemp", "gistemp_global_anom")
    assert g["ts"] == "2026-08-15" and g["value"] == 1.40
    assert latest("nasa_gistemp", "gistemp_tropics_annual_anom")["value"] == 0.86  # 2025


def test_gistemp_skips_stars():
    rows = N.parse_gistemp_monthly(fx("GLB.Ts+dSST.csv").decode())
    assert not any(r["ts"] == "2026-09-15" for r in rows)


# ----------------------------------------------------------------- Worldview


@respx.mock
async def test_worldview_snapshots_verified_and_fallback():
    def answer(request):
        # the Pacific East view has no data for the first date tried: next date works
        if "BBOX=-30.0,-180.0" in str(request.url) and "TIME=" in str(request.url) and \
                not answer.seen_east:
            answer.seen_east = True
            return httpx.Response(200, content=fx("wvs_nodata.jpg"),
                                  headers={"content-type": "image/jpeg"})
        return httpx.Response(200, content=fx("wvs_samui_truecolor.jpg"),
                              headers={"content-type": "image/jpeg"})
    answer.seen_east = False
    respx.get(url__startswith=N.WVS_URL).mock(side_effect=answer)
    res = await run(N.NasaWorldviewSnapshots())
    assert res["items"] == len(N.SNAPSHOTS)
    st = db.get_status("snapshots")["value"]
    ids = {i["id"]: i for i in st["items"]}
    assert set(ids) == {s["id"] for s in N.SNAPSHOTS}
    assert ids["pacific_ssta_east"]["date"] < ids["samui_truecolor"]["date"]
    assert ids["samui_truecolor"]["url"].startswith(N.WVS_URL + "?REQUEST=GetSnapshot")
    assert "LAYERS=VIIRS_NOAA20_CorrectedReflectance_TrueColor,Coastlines_15m" in \
        ids["samui_truecolor"]["url"]


@respx.mock
async def test_worldview_all_blank_is_an_error():
    respx.get(url__startswith=N.WVS_URL).mock(return_value=httpx.Response(
        200, content=fx("wvs_nodata.jpg"), headers={"content-type": "image/jpeg"}))
    async with httpx.AsyncClient() as c:
        res = await run_collector(N.NasaWorldviewSnapshots(), c)
    assert not res["ok"]
    assert db.get_status("snapshots") is None


# ----------------------------------------------------------------- CMR


@respx.mock
async def test_cmr_latency():
    def answer(request):
        sn = request.url.params["short_name"]
        if sn == "GPM_3IMERGHHE":
            return httpx.Response(200, content=fx("cmr_imerg_hh.json"))
        if sn == "NASA_SSH_REF_SIMPLE_GRID_V1":
            return httpx.Response(200, content=fx("cmr_empty.json"))
        return httpx.Response(200, content=fx("cmr_mur.json"))
    respx.get(url__startswith=N.CMR_GRANULES_URL).mock(side_effect=answer)
    await run(N.NasaCmrLatency())
    st = db.get_status("nasa_dataset_latency")["value"]
    by = {d["id"]: d for d in st["datasets"]}
    assert by["mur_sst"]["time_end"] == "2026-09-23T21:00:00.000Z"
    assert by["mur_sst"]["granule"].startswith("20260923090000-JPL-L4_GHRSST")
    assert by["imerg_30min"]["time_start"].startswith("2026-09-24")
    assert by["nasa_ssh_grid"]["state"] == "no_granules"
    assert by["mur_sst"]["lag_h"] > 0


def test_cmr_bad_payload():
    with pytest.raises(SourceChanged):
        N.parse_cmr_latest({"nope": 1}, N.CMR_DATASETS[0], __import__("datetime").datetime.now(
            __import__("datetime").UTC))


# ----------------------------------------------------------------- GRACE


@respx.mock
async def test_grace_drought_maps():
    respx.get(N.GRACE_DIR).mock(return_value=httpx.Response(
        200, content=fx("grace_globaldata_index.html")))
    respx.get(N.GRACE_DIR + "20260921/").mock(return_value=httpx.Response(
        200, content=fx("grace_20260921.html")))
    respx.head(url__regex=r".*/GRACE_GWS_AS_20260921\.png").mock(return_value=httpx.Response(
        200, headers={"last-modified": "Tue, 22 Sep 2026 16:12:36 GMT"}))
    await run(N.NasaGraceDrought())
    st = db.get_status("grace_drought_asia")["value"]
    assert st["date"] == "2026-09-21" and st["posted_at"] == "2026-09-22T16:12:36+00:00"
    assert [m["id"] for m in st["maps"]] == ["gws", "rtzsm", "sfsm"]
    assert st["maps"][0]["url"] == \
        "https://nasagrace.unl.edu/globaldata/20260921/GRACE_GWS_AS_20260921.png"
    items = db.query("SELECT published_at, kind FROM feed_items WHERE source='nasa_grace_drought'")
    assert items == [{"published_at": "2026-09-21", "kind": "research"}]


def test_grace_index_latest():
    assert N.parse_grace_index(fx("grace_globaldata_index.html").decode())[-1] == "20260921"


# ----------------------------------------------------------------- GMAO


@respx.mock
async def test_gmao_plumes(monkeypatch):
    def answer(request):
        if request.url.params["month"] == "Sep":
            body = fx("gmao_lookup_nino34_sep2026.json").decode()
            idx = request.url.params["field1"]
            fname = "nino1+2" if idx == "nino1.2" else idx
            return httpx.Response(200, text=body.replace("nino3.4_sep2026", f"{fname}_sep2026"))
        return httpx.Response(200, content=fx("gmao_lookup_oct2026_missing.json"))
    respx.get(N.GMAO_LOOKUP).mock(side_effect=answer)
    respx.get(url__startswith="https://gmao.gsfc.nasa.gov/media/").mock(
        return_value=httpx.Response(200, content=fx("gibs_flood_tile.png"), headers={
            "content-type": "image/png", "last-modified": "Wed, 02 Sep 2026 15:08:40 GMT"}))

    class Oct(N.datetime):
        @classmethod
        def now(cls, tz=None):
            return N.datetime(2026, 10, 3, tzinfo=tz)
    monkeypatch.setattr(N, "datetime", Oct)
    await run(N.NasaGmaoS2s())
    st = db.get_status("gmao_s2s_plume")["value"]
    assert st["release"] == "2026-09"  # October not released yet -> falls back
    assert st["posted_at"] == "2026-09-02T15:08:40+00:00"
    assert [p["index"] for p in st["plumes"]] == ["nino3.4", "nino3", "nino4", "nino1.2", "idm"]
    assert st["plumes"][0]["url"].endswith("/2026/sep/plumes/nino3.4_sep2026_plume_S2S.png")


# ----------------------------------------------------------------- EO


def test_eo_iotd_filter():
    items = N.parse_eo_iotd(fx("eo_image_of_the_day.rss"))
    titles = [i["title"] for i in items]
    assert "Lake Powell Drops to Record-Low Levels" in titles
    assert not any(re.search("Perseverance|Aurora", t) for t in titles)
    assert all(i["kind"] == "research" and i["published_at"] for i in items)


def test_earthdata_token_is_optional(monkeypatch):
    monkeypatch.delenv(N.EARTHDATA_TOKEN_ENV, raising=False)
    assert N.earthdata_token() is None
    assert all(not c.needs for c in N.COLLECTORS)
