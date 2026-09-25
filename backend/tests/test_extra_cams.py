"""Webcam collectors + /api/webcams against REAL payloads captured 2026-09-24 (no network).

Fixtures (tests/fixtures/cams/):
- ndbc_buoycams_subset.json: 7 rows of the real buoycams.php JSON (1 Atlantic, 3 Pacific
  with a photo, 3 Pacific without); image_heads.json: real HEAD headers of the images;
  ndbc_51002_W24A_2026_09_24_1310.jpg: a real BuoyCAM strip (for the snapshot proxy).
- jma_sat_img_se1.html / jma_sat_img_fd.html: real JMA MSC Himawari pages.
- oembed_*.json / .txt: real YouTube oEmbed answers (the .txt is the real 404 body).
- skyline_mancora.html (online) / skyline_thong_sala.html (marked OFFLINE): real pages.
- windy_openapi.json: Windy's real published OpenAPI document. No Windy key was
  available, so the Windy parser is tested on the example values of that document.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import cams_api, db
from app.collectors import extra_cams as X
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "cams"
NOW = datetime(2026, 9, 24, 14, 15, tzinfo=UTC)


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


@pytest.fixture(autouse=True)
def mem_db(monkeypatch):
    db.reset_for_tests()
    monkeypatch.setattr(X, "_now", lambda: NOW)
    cams_api._cache.clear()


async def run(col) -> dict:
    async with httpx.AsyncClient() as c:
        return await run_collector(col, c)


# --------------------------------------------------------------------------- parsers

def test_ndbc_parse_keeps_pacific_only():
    cams = X.parse_ndbc_buoycams(json.loads(fx("ndbc_buoycams_subset.json")))
    ids = {c["id"] for c in cams}
    assert "ndbc_41002" not in ids                      # Atlantic (Cape Hatteras)
    assert {"ndbc_51002", "ndbc_46070", "ndbc_46006"} <= ids  # 46070 is at 175.2 E
    b = next(c for c in cams if c["id"] == "ndbc_51002")
    assert b["snapshot_url"] == X.NDBC_IMG_BASE + "W24A_2026_09_24_1310.jpg"
    assert b["mode"] == "proxy" and b["snapshot_allowed"] and b["kind"] == "buoy"
    assert b["lat"] == 17.07 and b["lon"] == -157.755


def test_ndbc_image_time_from_file_name():
    assert X.ndbc_image_time("W24A_2026_09_24_1310.jpg") == datetime(2026, 9, 24, 13, 10,
                                                                     tzinfo=UTC)
    assert X.ndbc_image_time("nonsense.jpg") is None


def test_ndbc_bad_payload_is_source_changed():
    with pytest.raises(SourceChanged):
        X.parse_ndbc_buoycams({"error": "x"})


def test_jma_latest_time():
    hhmm, t = X.parse_jma_latest(fx("jma_sat_img_se1.html").decode())
    assert hhmm == "1350" and t == datetime(2026, 9, 24, 14, 0, tzinfo=UTC)
    with pytest.raises(SourceChanged):
        X.parse_jma_latest("<html>layout changed</html>")


def test_skyline_offline_flag():
    assert X.skyline_is_offline(fx("skyline_thong_sala.html").decode())
    assert not X.skyline_is_offline(fx("skyline_mancora.html").decode())


def test_every_stream_cam_is_complete_and_public_mode():
    ids = set()
    for c in X.STREAM_CATALOG:
        assert c["id"] not in ids
        ids.add(c["id"])
        assert c["kind"] in {"beach", "pier", "city", "airport", "buoy", "satellite", "traffic"}
        assert c["page_url"].startswith("http") and c["why"] and c["license_note"]
        assert c["publisher"] and c["lat"] is not None
        # no stream cam may be proxied: none of these owners allow frame reuse
        assert c["snapshot_allowed"] is False and c["mode"] in ("embed", "link")
        assert chr(0x2014) not in c["why"] + c["title"]  # rule 8: no em dashes


# --------------------------------------------------------------------------- image collector

def mock_images(router: respx.MockRouter) -> None:
    router.get(X.NDBC_BUOYCAMS_URL).mock(
        return_value=httpx.Response(200, content=fx("ndbc_buoycams_subset.json"),
                                    headers={"content-type": "text/html"}))
    heads = json.loads(fx("image_heads.json"))
    for url, h in heads.items():
        router.head(url).mock(return_value=httpx.Response(h["status"], headers=h["headers"]))
    router.get(X.JMA_PAGE.format(area="se1")).mock(
        return_value=httpx.Response(200, content=fx("jma_sat_img_se1.html")))
    router.get(X.JMA_PAGE.format(area="fd_")).mock(
        return_value=httpx.Response(200, content=fx("jma_sat_img_fd.html")))


@respx.mock
async def test_image_collector_end_to_end():
    mock_images(respx)
    res = await run(X.WebcamImages())
    assert res["ok"], res
    cams = {c["id"]: c for c in db.get_status("webcams")["value"]}
    b = cams["ndbc_51002"]
    assert b["status"] == "live" and b["ok"] and b["live_basis"] == "image_time"
    assert b["image_updated_at"] == "2026-09-24T13:10:00+00:00" and b["image_age_s"] == 3900
    assert cams["ndbc_46028"]["status"] == "offline" and not cams["ndbc_46028"]["ok"]
    h = cams["himawari_se1_b13"]
    assert h["snapshot_url"].endswith("/se1/se1_b13_1350.jpg") and h["status"] == "live"
    g = cams["goes18_fd_geocolor"]
    assert g["status"] == "live" and g["image_updated_at"] == "2026-09-24T14:07:12+00:00"
    assert res["items"] == sum(1 for c in cams.values() if c["ok"])


@respx.mock
async def test_old_images_are_stale_never_live(monkeypatch):
    mock_images(respx)
    monkeypatch.setattr(X, "_now", lambda: NOW + timedelta(days=1))
    await run(X.WebcamImages())
    cams = db.get_status("webcams")["value"]
    with_image = [c for c in cams if c["image_updated_at"]]
    assert with_image and all(c["status"] == "stale" and not c["ok"] for c in with_image)
    assert not [c for c in cams if c["status"] == "live"]


@respx.mock
async def test_failed_image_is_error_and_keeps_last_ok(monkeypatch):
    mock_images(respx)
    await run(X.WebcamImages())
    first_ok = next(c for c in db.get_status("webcams")["value"]
                    if c["id"] == "goes18_fd_ir")["last_ok"]
    assert first_ok == NOW.isoformat()
    respx.head(X.GOES_BASE.format(sat="GOES18", band="13")).mock(
        return_value=httpx.Response(404))
    monkeypatch.setattr(X, "_now", lambda: NOW + timedelta(minutes=30))
    await run(X.WebcamImages())
    c = next(c for c in db.get_status("webcams")["value"] if c["id"] == "goes18_fd_ir")
    assert c["status"] == "error" and not c["ok"] and c["last_ok"] == first_ok


# --------------------------------------------------------------------------- streams collector

def mock_streams(router: respx.MockRouter) -> None:
    def oembed(request):
        vid = request.url.params["url"].rsplit("=", 1)[-1]
        for name in (f"oembed_{vid}.json",):
            if (FIX / name).exists():
                return httpx.Response(200, content=fx(name),
                                      headers={"content-type": "application/json"})
        return httpx.Response(404, content=fx("oembed_unGBfW8m_9U.txt"))

    router.get(X.YT_OEMBED).mock(side_effect=oembed)

    def skyline(request):
        name = ("skyline_thong_sala.html" if "choengmon" in str(request.url)
                else "skyline_mancora.html")
        return httpx.Response(200, content=fx(name))

    router.get(url__startswith="https://www.skylinewebcams.com/").mock(side_effect=skyline)
    for c in X.STREAM_CATALOG:
        if c.get("_check") == "page":
            router.head(c["page_url"]).mock(return_value=httpx.Response(200))


@respx.mock
async def test_stream_collector_states():
    mock_streams(respx)
    res = await run(X.WebcamStreams())
    assert res["ok"], res
    cams = {c["id"]: c for c in db.get_status("webcams")["value"]}
    fv = cams["yt_CSp55hSd_6A"]
    assert fv["status"] == "reachable" and fv["ok"] and fv["mode"] == "embed"
    assert fv["embed_url"] == "https://www.youtube-nocookie.com/embed/CSp55hSd_6A"
    assert cams["yt_gtSsnmLXJV4"]["status"] == "reachable"   # publisher matches (Scuba Birds)
    gone = cams["yt_DwKCna1mumk"]                             # oEmbed 404 in this test
    assert gone["status"] == "offline" and not gone["ok"] and "removed" in gone["detail"]
    assert cams["skyline_mancora"]["status"] == "online"
    assert cams["skyline_choengmon_beach"]["status"] == "offline"
    assert cams["bma_traffic"]["status"] == "reachable" and cams["bma_traffic"]["mode"] == "link"
    assert not any(k.startswith("_") for c in cams.values() for k in c)


@respx.mock
async def test_publisher_change_is_flagged():
    body = json.loads(fx("oembed_CSp55hSd_6A.json"))
    body["author_name"] = "Someone Else"
    respx.get(X.YT_OEMBED).mock(return_value=httpx.Response(200, json=body))
    respx.get(url__startswith="https://www.skylinewebcams.com/").mock(
        return_value=httpx.Response(200, content=fx("skyline_mancora.html")))
    respx.head(url__regex=r".*").mock(return_value=httpx.Response(200))
    await run(X.WebcamStreams())
    yts = [c for c in db.get_status("webcams")["value"] if c["id"].startswith("yt_")]
    assert yts and all(c["status"] == "offline" and "re-verify" in c["detail"] for c in yts)


# --------------------------------------------------------------------------- Windy

async def test_windy_needs_config_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv(X.WINDY_KEY_ENV, raising=False)
    monkeypatch.setattr(X, "ROOT", tmp_path)
    res = await run(X.WindyWebcams())
    assert res["ok"] is False and res["needs_config"] == [X.WINDY_KEY_ENV]


def windy_example_payload() -> dict:
    """Assemble one webcam from the example values in Windy's real OpenAPI document."""
    sch = json.loads(fx("windy_openapi.json"))["components"]["schemas"]

    def ex(name):
        return {k: v["example"] for k, v in sch[name]["properties"].items() if "example" in v}

    w = ex("WebcamDto")
    w.update(location=ex("WebcamLocationDto"), player=ex("WebcamPlayerUrlsDto"),
             urls=ex("WebcamUrlsDto"))
    return {"total": 1, "webcams": [w]}


def test_windy_parse_documented_shape():
    [c] = X.parse_windy(windy_example_payload(), "samui")
    assert c["id"] == "windy_1179853135" and c["mode"] == "embed"
    assert c["lat"] == -33.84903 and c["place"].endswith("Australia")
    assert c["embed_url"].endswith("playerType=live")
    # the documented example's lastUpdatedOn is from 2012: stale, never live
    assert c["status"] == "stale" and not c["ok"]
    with pytest.raises(SourceChanged):
        X.parse_windy({"webcams": [{"webcamId": 1}]}, "samui")


@respx.mock
async def test_windy_collector_with_key(monkeypatch):
    monkeypatch.setenv(X.WINDY_KEY_ENV, "k")
    route = respx.get(X.WINDY_API).mock(
        return_value=httpx.Response(200, json=windy_example_payload()))
    res = await run(X.WindyWebcams())
    assert res["ok"], res
    assert route.calls[0].request.headers["x-windy-api-key"] == "k"
    ids = [c["id"] for c in db.get_status("webcams_windy")["value"]["webcams"]]
    assert ids == ["windy_1179853135"]  # deduplicated across the 3 area queries


# --------------------------------------------------------------------------- API

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(cams_api.router)
    return TestClient(app)


@respx.mock
async def test_api_filters_and_snapshot(client):
    mock_images(respx)
    mock_streams(respx)
    await run(X.WebcamImages())
    await run(X.WebcamStreams())

    r = client.get("/api/webcams", params={"kind": "buoy"}).json()
    assert r["count"] and all(c["kind"] == "buoy" for c in r["webcams"])
    b = next(c for c in r["webcams"] if c["id"] == "ndbc_51002")
    assert b["snapshot_proxy"] == "/api/webcams/ndbc_51002/snapshot"

    near = client.get("/api/webcams", params={"near": "9.512,100.013", "radius_km": 25}).json()
    assert near["count"] and all(c["distance_km"] <= 25 for c in near["webcams"])
    assert [c["distance_km"] for c in near["webcams"]] == sorted(
        c["distance_km"] for c in near["webcams"])
    assert not any(c["kind"] == "satellite" for c in near["webcams"])

    alive = client.get("/api/webcams", params={"alive": "true"}).json()["webcams"]
    assert alive and all(c["ok"] for c in alive)
    dead = client.get("/api/webcams", params={"alive": "false"}).json()["webcams"]
    assert any(c["id"] == "yt_DwKCna1mumk" for c in dead)
    conf = client.get("/api/webcams", params={"confirmed": "true"}).json()["webcams"]
    assert conf and {c["status"] for c in conf} <= {"live", "online"}

    assert client.get("/api/webcams", params={"near": "x"}).status_code == 422
    assert client.get("/api/webcams/nope").status_code == 404

    link_only = client.get("/api/webcams/yt_CSp55hSd_6A/snapshot")
    assert link_only.status_code == 409
    assert link_only.json()["detail"]["page_url"].startswith("https://www.youtube.com/")

    img = fx("ndbc_51002_W24A_2026_09_24_1310.jpg")
    up = respx.get(X.NDBC_IMG_BASE + "W24A_2026_09_24_1310.jpg").mock(
        return_value=httpx.Response(200, content=img, headers={
            "content-type": "image/jpeg", "last-modified": "Thu, 24 Sep 2026 13:32:29 GMT"}))
    s = client.get("/api/webcams/ndbc_51002/snapshot")
    assert s.status_code == 200 and s.content == img
    assert s.headers["content-type"] == "image/jpeg"
    assert s.headers["x-image-updated-at"] == "2026-09-24T13:10:00+00:00"
    assert "public domain" in s.headers["x-license"]
    client.get("/api/webcams/ndbc_51002/snapshot")
    assert up.call_count == 1  # served from the short cache
