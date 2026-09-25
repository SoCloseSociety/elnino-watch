"""Parsers of the Koh Samui collectors, fed with REAL payloads captured 2026-09-24
(tests/fixtures/local/*, some trimmed to a subset of the original rows)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors.base import SourceChanged, run_collector
from app.local import collectors as lc

FX = Path(__file__).parent / "fixtures" / "local"


def load(name: str):
    p = FX / name
    return p.read_text(encoding="utf-8") if p.suffix == ".xml" else json.loads(p.read_text())


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def test_forecast_daily_skips_nulls_and_flags_forecast():
    rows = lc.parse_daily(load("forecast.json"), lc.FORECAST_DAILY, today=date(2026, 9, 24))
    tmax = [r for r in rows if r["series"] == "samui_temp_max"]
    # Open-Meteo returned null temperatures for the oldest past days: not stored
    assert tmax[0]["ts"] == "2026-07-27"
    assert all(r["value"] is not None for r in rows)
    fut = [r for r in tmax if r["meta"]["forecast"]]
    assert fut[0]["ts"] == "2026-09-25" and fut[-1]["ts"] == "2026-10-09"
    assert {r["unit"] for r in rows if r["series"] == "samui_wind_gust_max"} == {"km/h"}


def test_forecast_format_change_raises():
    with pytest.raises(SourceChanged):
        lc.parse_daily({"hourly": {}}, lc.FORECAST_DAILY)
    with pytest.raises(SourceChanged):
        lc.parse_daily({"daily": {"time": []}}, lc.FORECAST_DAILY)


def test_air_hourly_utc():
    rows = lc.parse_hourly_utc(load("airquality.json"), lc.AIR_HOURLY,
                               now=datetime(2026, 9, 24, 12, tzinfo=UTC))
    pm = [r for r in rows if r["series"] == "samui_pm2_5"]
    assert pm[0]["ts"] == "2026-09-21T00:00:00+00:00"
    assert all(0 <= r["value"] < 500 for r in pm)
    assert any(r["meta"]["forecast"] for r in pm) and not pm[0]["meta"]["forecast"]
    with pytest.raises(SourceChanged):
        lc.parse_hourly_utc(load("airquality.json") | {"utc_offset_seconds": 25200},
                            lc.AIR_HOURLY)


def test_era5_recent():
    rows = lc.parse_daily(load("archive_recent.json"),
                          {"precipitation_sum": ("samui_era5_precip", "mm")})
    assert rows[-1]["ts"] == "2026-09-18"  # ERA5 lags ~6 days; later nulls are skipped
    assert rows[0]["meta"] is None


def test_build_climatology_from_real_era5():
    clim = lc.build_climatology(load("archive_clim_2019_2020.json"))
    assert len(clim["days"]) == 365 and "02-29" not in clim["days"]
    p, tx, tn, ax = clim["days"]["11-15"]
    assert p > clim["days"]["03-15"][0]  # NE monsoon wetter than the dry season
    assert 20 < tn < tx < 36 and ax > 25
    assert 800 < clim["annual_precip_mm"] < 3000
    assert clim["period"] == "2019-2020"


def test_seasonal_monthly():
    doc = lc.parse_seasonal_monthly(load("seasonal_monthly.json"))
    m0 = doc["months"][0]
    assert m0["month"] == "2026-09"
    assert m0["precip_pct_of_model_normal"] == round(100 * 301.5 / (301.5 - 47.2))
    assert len(doc["months"]) == 6
    with pytest.raises(SourceChanged):
        lc.parse_seasonal_monthly({"monthly": {"time": []}})


def test_thaiwater_samui_rain():
    res = lc.parse_thaiwater_samui_rain(load("thaiwater_rain24h_84.json"))
    assert res is not None
    names = {s["name"] for s in res["stations"]}
    assert "KO SAMUI" in names  # the TMD synoptic station 48550
    assert all(s["tambon"] for s in res["stations"])
    assert res["value"] == max(s["rain_24h"] for s in res["stations"])
    assert res["ts"].endswith("+00:00")
    with pytest.raises(SourceChanged):
        lc.parse_thaiwater_samui_rain({"result": "FAIL"})


def test_thaiwater_dams():
    dams = lc.parse_thaiwater_dams(load("thaiwater_main_dam.json"))
    assert [d["name"] for d in dams] == ["Ratchaprapa"]
    assert dams[0]["province"] == "Surat Thani" and 0 < dams[0]["storage_pct"] <= 100
    with pytest.raises(SourceChanged):
        lc.parse_thaiwater_dams({})


def test_tmd_storm_tracking():
    doc = lc.parse_tmd_storm_tracking(load("tmd_storm_tracking.xml"), today=date(2026, 9, 24))
    first = doc["items"][0]
    assert first["issue"] == "223/2569"
    assert first["until"] == "2026-09-27" and first["active"]
    assert first["heavy_rain"] and first["affects_samui"]
    assert not first["mentions_samui"]  # says "the South", not Samui by name
    seqs = [i["seq"] for i in doc["items"]]
    assert seqs == sorted(seqs, reverse=True)
    later = lc.parse_tmd_storm_tracking(load("tmd_storm_tracking.xml"), today=date(2026, 10, 5))
    assert not any(i["active"] for i in later["items"])


def test_tmd_until_parsing():
    assert lc._tmd_until("x (มีผลกระทบตั้งแต่วันที่ 23 - 27 กันยายน 2569) y") == date(2026, 9, 27)
    assert lc._tmd_until("no date") is None


@respx.mock
async def test_seasonal_collector_run_records_status():
    respx.get(url__startswith=lc.SEASONAL_URL).mock(
        return_value=httpx.Response(200, json=load("seasonal_monthly.json")))
    async with httpx.AsyncClient() as client:
        res = await run_collector(lc.OpenMeteoSamuiSeasonal(), client)
    assert res["ok"] and res["items"] == 6
    assert db.get_status("samui_seasonal")["value"]["months"][0]["month"] == "2026-09"


@respx.mock
async def test_forecast_collector_source_changed_is_recorded():
    respx.get(url__startswith=lc.FORECAST_URL).mock(
        return_value=httpx.Response(200, json={"error": True, "reason": "x"}))
    async with httpx.AsyncClient() as client:
        res = await run_collector(lc.OpenMeteoSamui(), client)
    assert not res["ok"]
    run = db.query("SELECT error FROM source_runs WHERE source='openmeteo_samui'")[0]
    assert run["error"].startswith("SourceChanged")


def test_tmd_ssl_context_keeps_verification():
    import ssl

    ctx = lc.tmd_ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    assert lc.TMD_INTERMEDIATE.is_file()


def test_tmd_andaman_waves_are_not_gulf_waves():
    doc = lc.parse_tmd_storm_tracking(load("tmd_storm_tracking.xml"), today=date(2026, 9, 20))
    andaman = next(i for i in doc["items"] if i["issue"] == "216/2569")
    assert andaman["strong_waves"] and not andaman["strong_waves_gulf"]
    assert not andaman["small_boats_ashore"]
    rain = next(i for i in doc["items"] if i["issue"] == "223/2569")
    assert not rain["strong_waves_gulf"] and rain["wave_m_max"] is None


def test_tmd_gulf_wave_wording():
    # TMD's usual Gulf wording (waves 2-3 m, small boats should stay ashore)
    gulf = lc._tmd_sea("คลื่นลมแรงบริเวณอ่าวไทย",
                       "อ่าวไทยมีคลื่นสูง 2-3 เมตร ขอให้เรือเล็กงดออกจากฝั่ง")
    assert gulf == {"strong_waves_gulf": True, "small_boats_ashore": True, "wave_m_max": 3.0}
    both = lc._tmd_sea("คลื่นลมแรงบริเวณทะเลอันดามันและอ่าวไทย", "")
    assert both["strong_waves_gulf"]
    unnamed = lc._tmd_sea("คลื่นลมแรง", "")
    assert unnamed["strong_waves_gulf"]  # sea not named: assume the Gulf (conservative)
    assert lc._tmd_sea("x", "คลื่นสูงกว่า 3 เมตร")["wave_m_max"] == 3.0


def test_pwa_notices_parser_real_payloads():
    items = lc.parse_pwa_notices(load("pwa_notices_all_branches.json"))
    assert len(items) == 44
    kinds = {i["kind"] for i in items}
    assert kinds == {"store_water", "pipe_burst", "no_supply"}
    assert {i["status"] for i in items} == {"in_progress", "done", "cancelled"}
    ext = next(i for i in items if i["branch"] == "เบตง")
    assert ext["start"] == "2026-09-24T10:00:00+00:00"   # 17:00 Bangkok
    assert ext["end"] == "2026-09-24T15:00:00+00:00"     # extended end 22:00 Bangkok
    assert all(i["url"].startswith("https://support1662.pwa.co.th/") for i in items)
    assert lc.parse_pwa_notices(load("pwa_notices_samui_1206.json")) == []
    with pytest.raises(SourceChanged):
        lc.parse_pwa_notices({"message": "eror"})


@respx.mock
async def test_pwa_collector_posts_samui_branch():
    route = respx.post(lc.PWA_NOTICES_URL).mock(
        return_value=httpx.Response(200, json=load("pwa_notices_samui_1206.json")))
    async with httpx.AsyncClient() as client:
        res = await run_collector(lc.PwaSamuiNotices(), client)
    assert res["ok"] and res["items"] == 0
    assert json.loads(route.calls[0].request.content)["ba"] == [lc.PWA_SAMUI_BA]
    st = db.get_status("pwa_samui_notices")["value"]
    assert st["items"] == [] and st["branch"] == "1206"
