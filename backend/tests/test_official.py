"""Official-bulletin collectors against REAL payloads captured 2026-09-24 (no network)."""

from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import official as O
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "official"
FIG3 = "https://ensoforecast.iri.columbia.edu/figure3_plot/2026/8"


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


def feed(source: str) -> list[dict]:
    return db.query("SELECT * FROM feed_items WHERE source=? ORDER BY published_at DESC",
                    (source,))


@respx.mock
async def test_cpc_alert_status():
    respx.get(O.CpcDiscussion.endpoint).mock(
        return_value=httpx.Response(200, content=fx("ensodisc.shtml"),
                                    headers={"content-type": "text/html; charset=windows-1252"}))
    await run(O.CpcDiscussion())
    st = db.get_status("cpc_alert")["value"]
    assert st["status"] == "El Niño Advisory"
    assert st["issued"] == "2026-09-10"
    assert st["next_issue"] == "2026-10-08"
    assert st["synopsis"].startswith("El Niño is strengthening, with a greater than 90% chance")
    assert "+3.0°C" in st["text_excerpt"]
    assert st["url"] == O.CpcDiscussion.endpoint
    items = feed("cpc_discussion")
    assert len(items) == 1 and items[0]["kind"] == "official"
    assert items[0]["ext_id"] == "2026-09-10"


def test_cpc_without_alert_label_is_source_changed():
    with pytest.raises(SourceChanged):
        O.parse_cpc_discussion("<html><p>Synopsis: x</p></html>", "u")


@respx.mock
async def test_iri_plume_probabilities_from_svg():
    respx.get(O.IriPlume.endpoint).mock(
        return_value=httpx.Response(200, content=fx("iri_current.html")))
    respx.get(FIG3).mock(return_value=httpx.Response(200, content=fx("iri_figure3.svg")))
    await run(O.IriPlume())
    st = db.get_status("iri_plume")["value"]
    assert st["issued"] == "2026-09-21"
    assert st["figure_url"] == FIG3
    assert st["title"] == "Mid-Sep 2026 CCSR/IRI Model-Based Probabilistic ENSO Forecasts"
    probs = {p["season"]: p for p in st["probabilities"]}
    assert list(probs) == ["SON", "OND", "NDJ", "DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ"]
    assert probs["SON"] == {"season": "SON", "la_nina": 0.0, "neutral": 0.0, "el_nino": 100.0}
    assert probs["AMJ"] == {"season": "AMJ", "la_nina": 0.0, "neutral": 10.0, "el_nino": 90.0}
    assert probs["MJJ"] == {"season": "MJJ", "la_nina": 2.0, "neutral": 37.0, "el_nino": 61.0}
    for p in st["probabilities"]:
        assert abs(p["la_nina"] + p["neutral"] + p["el_nino"] - 100) < 0.5
    assert "61% by mid-2027" in st["summary"]  # the page's own text agrees with the bars


@respx.mock
async def test_jma_outlook():
    respx.get(O.JmaOutlook.endpoint).mock(
        return_value=httpx.Response(200, content=fx("jma_outlook.html")))
    await run(O.JmaOutlook())
    st = db.get_status("jma_outlook")["value"]
    assert st["issued"] == "2026-09-09"
    assert st["next_issue"] == "2026-10-09"
    assert st["period"] == "September 2026 - March 2027"
    assert "virtually certain (100%)" in st["status"]
    assert "+3.4°C" in st["text_excerpt"]
    assert feed("jma_outlook")[0]["ext_id"] == "2026-09-09"


@respx.mock
async def test_climategov_rss():
    respx.get(O.ClimateGovEnsoBlog.endpoint).mock(
        return_value=httpx.Response(200, content=fx("climategov_enso.rss")))
    res = await run(O.ClimateGovEnsoBlog())
    assert res["items"] == 10
    top = feed("climategov_enso_blog")[0]
    assert top["title"] == "A 'Hitchhiker's Guide' to the June 2025 ENSO update"
    assert top["published_at"] == "2025-06-12T12:00:00+00:00"
    assert top["author"] == "Emily Becker" and top["kind"] == "official"


@respx.mock
async def test_wmo_updates_and_news():
    respx.get(O.WmoEnsoUpdates.endpoint).mock(
        return_value=httpx.Response(200, content=fx("wmo_updates.html")))
    respx.get(O.WmoEnsoUpdates.theme_url).mock(
        return_value=httpx.Response(200, content=fx("wmo_theme.html")))
    res = await run(O.WmoEnsoUpdates())
    items = {i["ext_id"]: i for i in feed("wmo_enso")}
    assert res["items"] == len(items)
    upd = items["august-2026"]
    assert upd["title"] == "El Niño/La Niña Update (August 2026)"
    assert upd["published_at"] == "2026-09-03"
    assert upd["url"] == ("https://wmo.int/resources/publication-series/"
                          "el-ninola-nina-updates/august-2026")
    assert "publication" in upd["tags"]
    assert items["strong-el-nino-expected-intensify"]["published_at"] == "2026-07-31"
    # press release listed on both pages under different paths -> stored once
    assert "el-nino-set-become-very-strong-raising-risks-of-extreme-weather-2027" in items
    # non-ENSO cards are dropped
    assert "earth-has-hottest-august-record" not in items
