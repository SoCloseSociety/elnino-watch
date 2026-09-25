"""Map layer catalog: date resolution from REAL GIBS capabilities, RainViewer frame, API.

Fixtures (captured 2026-09-24): gibs_capabilities_subset.xml = the real WMTS
capabilities reduced to the <Layer> blocks we serve; rainviewer_weather_maps.json = the
real weather-maps.json.
"""

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import layers as L
from app import layers_api

FIX = Path(__file__).parent / "fixtures" / "layers"
TODAY = date(2026, 9, 24)


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


@pytest.fixture(autouse=True)
def fresh_caches():
    for c in (layers_api._caps, layers_api._radar, layers_api._verify):
        c.value = None


def dims() -> dict:
    return L.parse_time_dimensions(fx("gibs_capabilities_subset.xml").decode(),
                                   {x["gibs_id"] for x in L.LAYERS})


def test_catalog_shape():
    ids = [x["id"] for x in L.LAYERS]
    assert len(ids) == len(set(ids))
    for x in L.LAYERS:
        assert {"id", "title", "url_template", "max_zoom", "format", "legend_url",
                "attribution", "description", "default_date_offset_days"} <= set(x)
        assert x["url_template"].startswith("https://gibs.earthdata.nasa.gov/wmts/epsg3857/")
        assert ("{time}" in x["url_template"]) == (x["time_mode"] == "daily")
        assert "\u2014" not in x["description"]  # no em dash


def test_every_catalog_layer_is_in_capabilities():
    # The captured capabilities subset covers the core catalog; the extra layers
    # (layers_extra.py, merged by layers_api) are verified in test_extra_nasa.py.
    from app.layers_extra import EXTRA_LAYERS
    extra = {x["gibs_id"] for x in EXTRA_LAYERS}
    d = dims()
    assert set(d) == {x["gibs_id"] for x in L.LAYERS} - extra


def test_dates_come_from_capabilities():
    d = dims()
    by = {x["id"]: x for x in L.LAYERS}
    assert L.resolve_date(by["sst_anomaly"], d, TODAY) == ("2026-09-23", "capabilities")
    # SMAP skips days: the capabilities default (09-21) wins over "today - 3"
    assert L.resolve_date(by["soil_moisture"], d, TODAY) == ("2026-09-21", "capabilities")
    # swath imagery: default is today (partial mosaic) -> yesterday, which exists
    assert L.resolve_date(by["truecolor_viirs"], d, TODAY) == ("2026-09-23", "capabilities")
    assert L.resolve_date(by["chlorophyll"], d, TODAY) == ("2026-09-23", "capabilities")
    assert L.resolve_date(by["ir_himawari"], d, TODAY) == (None, "latest")


def test_offset_fallback_without_capabilities():
    lay = L.LAYERS_BY_ID["soil_moisture"]
    assert L.resolve_date(lay, None, TODAY) == ("2026-09-21", "offset")


def test_rainviewer_parse():
    import json
    r = L.parse_rainviewer(json.loads(fx("rainviewer_weather_maps.json")))
    assert r["url_template"] == ("https://tilecache.rainviewer.com/v2/radar/209ca56c29bb"
                                 "/256/{z}/{x}/{y}/2/1_1.png")
    assert r["time"] == "2026-09-24T12:30:00+00:00" and r["max_zoom"] == 7


def test_rainviewer_bad_payload():
    with pytest.raises(ValueError):
        L.parse_rainviewer({"host": "x", "radar": {"past": []}})


@respx.mock
def test_api_layers():
    respx.get(L.GIBS_CAPS_URL).mock(
        return_value=httpx.Response(200, content=fx("gibs_capabilities_subset.xml")))
    respx.get(L.RAINVIEWER_URL).mock(
        return_value=httpx.Response(200, content=fx("rainviewer_weather_maps.json")))
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(layers_api.router)
    body = TestClient(app).get("/api/layers").json()
    assert body["errors"] == {}
    by = {x["id"]: x for x in body["layers"]}
    assert set(by) == {x["id"] for x in L.LAYERS} | {"radar_rainviewer"}
    sst = by["sst_anomaly"]
    assert sst["date_source"] == "capabilities"
    assert "{time}" not in sst["tiles"] and "/default/20" in sst["tiles"]
    assert sst["tiles"].endswith("/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png")
    assert by["radar_rainviewer"]["tiles"].startswith("https://tilecache.rainviewer.com/")


@respx.mock
def test_api_layers_reports_upstream_failure():
    respx.get(L.GIBS_CAPS_URL).mock(return_value=httpx.Response(503))
    respx.get(L.RAINVIEWER_URL).mock(return_value=httpx.Response(500))
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(layers_api.router)
    body = TestClient(app).get("/api/layers").json()
    assert set(body["errors"]) == {"gibs_capabilities", "rainviewer"}
    assert all(x["date_source"] in ("offset", "latest") for x in body["layers"])
    assert "radar_rainviewer" not in {x["id"] for x in body["layers"]}


def test_probe_url_fills_placeholders():
    lay = L.LAYERS_BY_ID["sst"]
    u = L.probe_url(lay, "2026-09-23")
    assert u.endswith("/2026-09-23/GoogleMapsCompatible_Level7/3/3/6.png")
