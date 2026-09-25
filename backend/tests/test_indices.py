"""Index collectors against REAL payloads captured 2026-09-24 (no network)."""

from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import indices as I
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "indices"


def fx(name: str) -> str:
    return (FIX / name).read_text(encoding="latin-1")


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def latest(source: str, series: str) -> dict:
    rows = db.query(
        "SELECT ts, value, meta FROM observations WHERE source=? AND series=? "
        "ORDER BY ts DESC LIMIT 1", (source, series))
    assert rows, f"no {series} stored"
    return rows[0]


async def run(col) -> dict:
    async with httpx.AsyncClient() as c:
        res = await run_collector(col, c)
    assert res["ok"], res
    return res


@respx.mock
@pytest.mark.parametrize("cls,fixture", [
    (I.CpcOni, "oni.ascii.txt"), (I.CpcRoni, "RONI.ascii.txt"),
    (I.CpcWeeklySst, "wksst9120.for"), (I.CpcSoi, "soi.txt"), (I.PslMei, "meiv2.data"),
    (I.CrWorldSst, "oisst2.1_world2_sst_day.json"),
    (I.CrNino34Daily, "oisst2.1_nino3.4_sst_day.json"),
])
async def test_http_collectors_store_rows(cls, fixture):
    respx.get(cls.endpoint).mock(return_value=httpx.Response(200, text=fx(fixture)))
    res = await run(cls())
    assert res["items"] > 0
    run_row = db.query("SELECT * FROM source_runs WHERE source=?", (cls.name,))[0]
    assert run_row["ok"] == 1 and run_row["http_status"] == 200


@respx.mock
async def test_oni_jja_2026_is_1_80():
    respx.get(I.CpcOni.endpoint).mock(return_value=httpx.Response(200, text=fx("oni.ascii.txt")))
    await run(I.CpcOni())
    row = latest("cpc_oni", "oni")
    assert row["ts"] == "2026-07-15" and row["value"] == 1.80
    assert row["meta"] == {"season": "JJA 2026"}
    assert latest("cpc_oni", "oni_total")["value"] == 29.09
    # DJF uses the center month (January) of its labelled year
    djf = db.query("SELECT ts FROM observations WHERE series='oni' AND meta LIKE '%DJF 2026%'")
    assert djf[0]["ts"] == "2026-01-15"


def test_roni_latest():
    rows = I.parse_roni(fx("RONI.ascii.txt"))
    assert rows[-1] == {"series": "roni", "ts": "2026-07-15", "value": 1.36, "unit": "degC",
                        "meta": {"season": "JJA 2026"}}


def test_weekly_sst_touching_fields():
    rows = {(r["series"], r["ts"]): r["value"] for r in I.parse_weekly_sst(fx("wksst9120.for"))}
    assert rows[("nino34_weekly_anom", "2026-09-16")] == 3.0
    assert rows[("nino34_weekly_sst", "2026-09-16")] == 29.6
    assert rows[("nino12_weekly_anom", "2026-09-16")] == 4.6
    assert rows[("nino4_weekly_anom", "2026-09-09")] == 0.9
    # "20.6-0.1" is two fields
    assert rows[("nino12_weekly_anom", "1981-09-02")] == -0.1


def test_cpc_soi_uses_standardized_table_and_skips_missing():
    rows = I.parse_cpc_soi(fx("soi.txt"))
    by_ts = {r["ts"]: r["value"] for r in rows}
    assert by_ts["2026-07-15"] == -2.4      # standardized (anomaly table says -4.0)
    assert by_ts["2026-08-15"] == -1.1
    assert "2026-09-15" not in by_ts        # -999.9
    assert by_ts["1951-01-15"] == 1.5
    assert all(v > -999 for v in by_ts.values())


def test_mei_bimonthly():
    rows = I.parse_mei(fx("meiv2.data"))
    last = rows[-1]
    assert last["ts"] == "2026-08-01" and last["value"] == 2.54
    assert last["meta"] == {"season": "JA 2026"}
    assert rows[0]["ts"] == "1979-01-01" and rows[0]["meta"]["season"] == "DJ 1979"


async def test_bom_soi_via_ftp(monkeypatch):
    monkeypatch.setattr(I.BomSoi, "fetch", lambda self: fx("bom_soiplaintext.html"))
    res = await run(I.BomSoi())
    assert res["items"] > 0
    row = latest("bom_soi", "bom_soi")
    assert row["ts"] == "2026-08-15" and row["value"] == -14.6


def test_bom_soi_block_page_is_source_changed():
    blocked = "<p>Your access is blocked due to the detection of a potential automated</p>"
    with pytest.raises(SourceChanged):
        I.parse_bom_soi(blocked)


def test_world_sst_daily_with_preliminary_and_clim():
    import json

    rows = I.parse_cr_daily(json.loads(fx("oisst2.1_world2_sst_day.json")),
                            I.CrWorldSst.series)
    daily = {r["ts"]: r for r in rows if r["series"] == "world_sst_daily"}
    assert daily["2026-09-07"]["value"] == 21.179 and daily["2026-09-07"]["meta"] is None
    assert daily["2026-09-22"]["value"] == 21.136
    assert daily["2026-09-22"]["meta"] == {"preliminary": True}
    assert "2026-09-23" not in daily
    assert daily["2025-12-31"]["value"] is not None
    clim = {r["ts"]: r["value"] for r in rows if r["series"] == "world_sst_clim"}
    assert max(clim) == "2026-09-22"  # never future-dated
    anom = {r["ts"]: r["value"] for r in rows if r["series"] == "world_sst_anom"}
    assert anom["2026-09-22"] == round(21.136 - clim["2026-09-22"], 3)


def test_nino34_daily():
    import json

    rows = I.parse_cr_daily(json.loads(fx("oisst2.1_nino3.4_sst_day.json")),
                            I.CrNino34Daily.series)
    daily = {r["ts"]: r["value"] for r in rows if r["series"] == "nino34_daily_sst"}
    anom = {r["ts"]: r["value"] for r in rows if r["series"] == "nino34_daily_anom"}
    assert daily["2026-09-07"] == 29.555
    assert anom["2026-09-07"] == 2.837
    assert 2.5 < anom["2026-09-22"] < 3.5  # consistent with CPC weekly +3.0


@respx.mock
async def test_format_change_is_an_error():
    respx.get(I.CpcOni.endpoint).mock(return_value=httpx.Response(200, text="<html>moved</html>"))
    async with httpx.AsyncClient() as c:
        res = await run_collector(I.CpcOni(), c)
    assert not res["ok"]
    err = db.query("SELECT error FROM source_runs WHERE source='cpc_oni'")[0]["error"]
    assert err.startswith("SourceChanged")
