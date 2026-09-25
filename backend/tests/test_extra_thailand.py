"""extra_thailand collectors against REAL payloads captured 2026-09-24 (no network)."""

from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import extra_thailand as T
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "extra"


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


@respx.mock
async def test_air4thai_nearest_station():
    respx.get(T.AIR4THAI_URL).mock(return_value=httpx.Response(200, content=fx(
        "air4thai_all.json")))
    await run(T.Air4ThaiSouth())
    st = db.get_status("air4thai_samui")["value"]
    assert st["station"] == "42t" and st["name"] == "Environment Agency Section 14, Surat Thani"
    assert 80 < st["distance_km"] < 95
    assert st["pm25"] == 7.0 and st["aqi"] == 12.0 and st["band"] == "very_good"
    assert st["observed_at"] == "2026-09-24T10:00:00+00:00"  # 17:00 Bangkok time
    assert st["pm10"] is None  # -1 = not measured: never stored as a number
    assert len(st["stations"]) == 8
    rows = db.query("SELECT * FROM observations WHERE series='air4thai_42t_pm25'")
    assert rows[0]["value"] == 7.0 and rows[0]["unit"] == "ug/m3"
    assert not db.query("SELECT 1 FROM observations WHERE series LIKE 'air4thai_42t_pm10'")


def test_air4thai_band():
    assert T.thai_aqi_band(12)[0] == "very_good"
    assert T.thai_aqi_band(75)[0] == "moderate"
    assert T.thai_aqi_band(150) == ("unhealthy", "Starting to affect health")
    assert T.thai_aqi_band(-1) == (None, None)


def test_air4thai_ssl_context_builds():
    ctx = T.air4thai_ssl_context()
    subjects = [dict(x[0] for x in c["subject"]).get("commonName") for c in ctx.get_ca_certs()]
    assert "YR1" in subjects and "Root YR" in subjects


def test_air4thai_bad_payload():
    with pytest.raises(SourceChanged):
        T.parse_air4thai({"error": "x"})


@respx.mock
async def test_asmc_outlook():
    respx.get(T.ASMC_OUTLOOK_URL).mock(return_value=httpx.Response(200, content=fx(
        "asmc_seasonal_outlook.html")))
    await run(T.AsmcSeasonalOutlook())
    v = db.get_status("asmc_seasonal_outlook")["value"]
    assert v["title"] == "Seasonal Forecast for September- November 2026"
    assert v["updated"] == "2026-09-02"
    assert v["overview"][1].startswith("For September 2026, below-normal rainfall is predicted")
    assert v["mainland_sea"][0].startswith("For Mainland Southeast Asia")
    assert any("Monthly Rainfall Outlook" in s for s in v["sections"])
    it = db.query("SELECT * FROM feed_items WHERE source='asmc_seasonal_outlook'")[0]
    assert it["kind"] == "official" and it["ext_id"] == "2026-09-02"
    assert "enso" in it["tags"] and "haze" in it["tags"]


def test_asmc_changed_page():
    with pytest.raises(SourceChanged):
        T.parse_asmc_outlook("<html><h1>Seasonal Outlook</h1></html>")
