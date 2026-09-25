"""extra_ocean collectors against REAL payloads captured 2026-09-24 (no network)."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import extra_ocean as O
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


def latest(source: str, series: str) -> dict:
    return db.query("SELECT * FROM observations WHERE source=? AND series=? ORDER BY ts DESC "
                    "LIMIT 1", (source, series))[0]


@respx.mock
async def test_cpc_enso_probs_status(monkeypatch):
    respx.get(O.CPC_PROBS_URL).mock(return_value=httpx.Response(200, content=fx("cpc_probs.html")))
    respx.get(O.CPC_STRENGTHS_URL).mock(
        return_value=httpx.Response(200, content=fx("cpc_strengths.html")))
    await run(O.CpcEnsoProbs())
    st = db.get_status("cpc_enso_probs")
    v = st["value"]
    assert v["issued"] == "2026-09"
    probs = {p["season"]: p for p in v["probabilities"]}
    assert probs["ASO"] == {"season": "ASO", "months": "Aug Sep Oct", "la_nina": 0.0,
                            "neutral": 0.0, "el_nino": 100.0}
    assert probs["AMJ"]["neutral"] == 55.0 and probs["AMJ"]["el_nino"] == 43.0
    strengths = {s["season"]: s["categories"] for s in v["strengths"]}
    assert strengths["SON"]["el_nino_very_strong"] == 97.0
    assert strengths["SON"]["el_nino_strong"] == 3.0
    assert strengths["JFM"]["el_nino_strong"] == 39.0
    assert list(strengths) == ["ASO", "SON", "OND", "NDJ", "DJF", "JFM", "FMA", "MAM", "AMJ"]
    assert "Very strong El Nino" in v["summary"]
    # a second identical run does not bump updated_at (freshness = last new issue)
    first = st["updated_at"]
    monkeypatch.setattr(db, "now_iso", lambda: "2099-01-01T00:00:00+00:00")
    await run(O.CpcEnsoProbs())
    assert db.get_status("cpc_enso_probs")["updated_at"] == first


def test_cpc_probs_changed_layout_is_source_changed():
    with pytest.raises(SourceChanged):
        O.parse_cpc_enso_probs(fx("cpc_probs.html").decode(), "<html>no table</html>")
    broken = fx("cpc_strengths.html").decode().replace("<td>77</td>", "")
    with pytest.raises(SourceChanged):
        O.parse_cpc_enso_probs(fx("cpc_probs.html").decode(), broken)


@respx.mock
async def test_heat_content():
    respx.get(O.CPC_HC_URL).mock(
        return_value=httpx.Response(200, content=fx("heat_content_index.txt")))
    await run(O.CpcHeatContent())
    r = latest("cpc_heat_content", "heat_content_180w_100w_anom")
    assert (r["ts"], r["value"], r["unit"]) == ("2026-08-15", 3.23, "degC")
    assert latest("cpc_heat_content", "heat_content_130e_80w_anom")["value"] == 2.19


def test_heat_content_bad_header():
    with pytest.raises(SourceChanged):
        O.parse_heat_content("something else\n1979 1 .5 .4 .3\n")


@respx.mock
async def test_pmel_wwv():
    for f in O.PMEL_FILES:
        respx.get(O.PMEL_BASE + f).mock(return_value=httpx.Response(200, content=fx(f"pmel_{f}")))
    await run(O.PmelWwv())
    r = latest("pmel_wwv", "wwv_anom")
    assert r["ts"] == "2026-08-15" and r["value"] == pytest.approx(3.4597, abs=1e-4)
    assert r["unit"] == "1e14 m3" and r["meta"]["region"] == "5N-5S,120E-80W"
    assert latest("pmel_wwv", "wwv_east_anom")["value"] == pytest.approx(4.0089, abs=1e-4)
    assert latest("pmel_wwv", "t300_east_anom")["value"] == pytest.approx(2.8943, abs=1e-4)
    assert latest("pmel_wwv", "wwv_total")["value"] == pytest.approx(27.2922, abs=1e-4)


def test_pmel_wrong_file_is_source_changed():
    with pytest.raises(SourceChanged):
        O.parse_pmel(fx("pmel_t300.dat").decode(), "wwv.dat")


@respx.mock
async def test_jma_iod_and_nino_west():
    for key in O.JMA_SERIES:
        respx.get(O.JMA_IDX + key + "/anomaly").mock(
            return_value=httpx.Response(200, content=fx(f"jma_{key}_anomaly.txt")))
    await run(O.JmaSstIndices())
    dmi = latest("jma_sst_indices", "dmi_jma_anom")
    assert (dmi["ts"], dmi["value"]) == ("2026-08-15", 0.37)  # Sep = 99.9 -> skipped
    assert latest("jma_sst_indices", "nino3_jma_anom")["value"] == 3.5
    assert latest("jma_sst_indices", "nino_west_jma_anom")["value"] == 0.1
    assert latest("jma_sst_indices", "iod_west_jma_anom")["meta"]["region"] == "10N-10S, 50E-70E"


@respx.mock
async def test_ecmwf_plume():
    respx.get(O.ECMWF_AXIS_URL).mock(
        return_value=httpx.Response(200, content=fx("ecmwf_plume_axis.json")))
    respx.get(O.ECMWF_PRODUCT_URL).mock(
        return_value=httpx.Response(200, content=fx("ecmwf_plume_nino34.json")))
    await run(O.EcmwfNinoPlume())
    v = db.get_status("ecmwf_nino_plume")["value"]
    assert v["issued"] == "2026-09-01" and v["label"] == "Sep 2026"
    assert v["images"]["nino34"].startswith("https://charts.ecmwf.int/content/")
    req = respx.calls[1].request
    assert req.url.params["base_time"] == "2026-09-01T00:00:00Z"
    assert req.url.params["nino_area"] == "NINO3-4"


def test_ecmwf_error_payload_is_source_changed():
    with pytest.raises(SourceChanged):
        O.parse_ecmwf_product(json.loads('{"error": ["nino_area NINO3.4 is not available"]}'))
