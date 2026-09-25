"""SEO layer (app/seo.py): server-rendered <head> + crawler summary per route, JSON-LD,
sitemap, robots, Open Graph card, IndexNow gating, CSP hashes. Never hits the network."""

from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path

os.environ.setdefault("SCHEDULER", "false")

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db, seo
from app.config import settings
from app.main import app

c = TestClient(app)


@pytest.fixture(autouse=True)
def fresh(monkeypatch, tmp_path):
    db.reset_for_tests()
    seo.invalidate_caches()
    seo._learn_cache = None
    monkeypatch.setattr(settings, "public_mode", False)
    monkeypatch.setattr(settings, "public_origin", "https://elnino.example.org")
    monkeypatch.setattr(settings, "indexnow_key", "")
    # a tiny Learn export of our own, so the tests never depend on the frontend build
    d = tmp_path / "seo"
    d.mkdir()
    (d / "topics.json").write_text(json.dumps({
        "generated_at": "2026-09-24T10:00:00+00:00", "count": 2,
        "categories": [{"id": "indices", "label": "Indices", "count": 2}],
        "topics": [
            {"id": "oni", "title": "ONI (Oceanic Nino Index)", "category": "indices",
             "category_label": "Indices",
             "short": "The 3-month running average of the Nino 3.4 anomaly, published monthly "
                      "by NOAA. +0.5 °C or more = El Nino threshold.",
             "body": "The ONI is NOAA's long-standing index.\n\n- It uses ERSST.\n- Base periods move.",
             "how_to_read": "Positive = warm.", "why_it_matters": "It sets the Samui ENSO factor.",
             "example": "", "thresholds": {"columns": ["ONI", "Phase"], "rows": [["+0.5", "El Nino"]]},
             "related": [{"id": "roni", "title": "RONI"}],
             "sources": [{"title": "NOAA CPC ONI", "url": "https://www.cpc.ncep.noaa.gov/x"}],
             "aliases": []},
            {"id": "roni", "title": "RONI", "category": "indices", "category_label": "Indices",
             "short": "Relative ONI.", "body": "Body.", "how_to_read": "", "why_it_matters": "",
             "example": "", "thresholds": None, "related": [], "sources": [], "aliases": []},
        ]}))
    (d / "faq.json").write_text(json.dumps({"generated_at": "2026-09-24T10:00:00+00:00", "items": [
        {"id": "no-rain", "question": "Does El Nino mean no rain on Samui?",
         "answer": "No. **It tilts** the odds.", "answer_text": "No. It tilts the odds.",
         "topics": []}]}))
    (d / "myths.json").write_text(json.dumps({"generated_at": "2026-09-24T10:00:00+00:00",
                                               "items": [{"myth": "M", "fact": "F", "topics": []}]}))
    monkeypatch.setattr(seo, "SEO_DATA_DIRS", (d,))


def seed():
    db.upsert_observations("cpc_oni", [
        {"series": "oni", "ts": "2026-06-15", "value": 1.39, "unit": "degC"},
        {"series": "oni", "ts": "2026-07-15", "value": 1.80, "unit": "degC"}])
    db.upsert_observations("cpc_roni", [{"series": "roni", "ts": "2026-07-15", "value": 1.36,
                                          "unit": "degC"}])
    db.upsert_observations("cpc_weekly_sst", [
        {"series": "nino34_weekly_anom", "ts": "2026-09-16", "value": 3.0, "unit": "degC"},
        {"series": "nino34_weekly_sst", "ts": "2026-09-16", "value": 29.6, "unit": "degC"},
        # a future-dated row must never become "the latest"
        {"series": "nino34_weekly_anom", "ts": "2099-01-01", "value": 9.9, "unit": "degC"}])
    db.set_status("cpc_alert", {"status": "El Niño Advisory", "issued": "2026-09-10",
                                "synopsis": "El Niño is strengthening.", "url": "https://cpc/x"})
    db.set_status("iri_plume", {"issued": "2026-09-21", "probabilities": [
        {"season": "SON", "la_nina": 0.0, "neutral": 0.0, "el_nino": 100.0},
        {"season": "OND", "la_nina": 0.0, "neutral": 2.0, "el_nino": 98.0}]})
    db.set_status("local_risk", {
        "level": 2, "level_key": "prepare", "level_label": "Prepare",
        "headline": "Prepare -- strong El Nino. No immediate threat on Samui.",
        "evaluated_at": "2026-09-24T16:57:46+00:00", "home": {"name": "Maenam, Koh Samui"},
        "factors": [{"id": "water", "label": "Water supply", "level_key": "normal", "value": 103,
                     "unit_label": "% of normal", "threshold": "< 60 %",
                     "as_of": "2026-09-18", "source": "ERA5", "url": "https://x/era5"}],
        "actions": [{"level_key": "prepare", "text": "Fill the tank."}],
        "triggers": [{"level_key": "act", "text": "PWA rationing notice."}]})
    db.set_status("briefing", {"generated_at": "2026-09-24T14:43:52+00:00", "headline": "H",
                               "sections": [{"id": "enso", "title": "ENSO state",
                                             "bullets": ["ONI +1.80 °C (JJA 2026)"]}]})
    db.record_run("cpc_oni", "2026-09-24T16:00:00+00:00", True, items=1)
    db.upsert_feed_items("noaa_cpc", [{"ext_id": "1", "kind": "official", "title": "ENSO update",
                                       "url": "https://cpc/u", "published_at": "2026-09-10"}])
    seo.invalidate_caches()


def head(html: str) -> str:
    return html.split("</head>", 1)[0]


# ------------------------------------------------------------------ metadata


def test_route_metadata_lengths():
    for path, m in seo.ROUTES.items():
        assert len(m["title"]) <= seo.TITLE_MAX, (path, len(m["title"]))
        assert seo.DESC_MIN <= len(m["description"]) <= seo.DESC_MAX, (path, len(m["description"]))
        assert "\u2014" not in m["title"] + m["description"]


def test_topic_metadata_fits():
    t = seo.learn_content()["topics"]["oni"]
    m = seo.topic_meta(t)
    assert len(m["title"]) <= seo.TITLE_MAX
    assert len(m["description"]) <= seo.DESC_MAX
    assert m["description"].startswith("The 3-month running average")


def test_home_head_and_summary_use_real_values():
    seed()
    r = c.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    h = head(r.text)
    assert "<title>El Nino 2026-27 Live Tracker: ONI, Nino 3.4, Forecasts</title>" in h
    assert '<link rel="canonical" href="https://elnino.example.org/">' in h
    assert 'hreflang="en" href="https://elnino.example.org/"' in h
    assert 'hreflang="x-default"' in h
    assert '<meta property="og:url" content="https://elnino.example.org/">' in h
    assert '<meta property="og:image" content="https://elnino.example.org/og/current.png">' in h
    assert '<meta name="twitter:card" content="summary_large_image">' in h
    assert h.count('<meta name="description"') == 1
    assert 'og:image:alt" content="El Nino Watch: ONI +1.80 °C (JJA 2026), RONI +1.36 °C, ' in h
    # live facts with their periods and as-of dates, inside #root (crawler-visible)
    body = r.text.split('<div id="root">', 1)[1]
    assert '<div id="prerender">' in body
    assert "+1.80 °C, JJA 2026 (previous +1.39 °C)" in body
    assert "+3.0 °C anomaly, week of 16 Sep 2026 (SST 29.6 °C)" in body
    assert "+9.9" not in body  # the future row is not "current"
    assert "El Niño Advisory (issued 10 Sep 2026)" in body
    assert "SON: El Nino 100%, neutral 0%, La Nina 0%" in body
    assert "Prepare (evaluated 24 Sep 2026 16:57 UTC)" in body
    # "Data updated" = the newest successful run, whose finished_at is written by record_run
    # at insert time (so it is "today", whatever day the suite runs on)
    newest = db.query("SELECT MAX(finished_at) AS t FROM source_runs WHERE ok=1")[0]["t"]
    assert f"Data updated</dt><dd>{seo._fmt_dt(newest)}" in body
    assert "<noscript>" in body
    # internal links to every section for crawl discovery
    for p in seo.ROUTES:
        assert f'href="{p}"' in body


def test_template_comments_cannot_break_the_page(monkeypatch, tmp_path):
    """A comment mentioning <title> in index.html once turned the whole page into a
    comment (the title regex matched from inside it). Comments are stripped first."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="UTF-8">'
        "<!-- the server replaces <title> and <meta name=\"description\"> per route -->"
        "<title>Dev</title><script>var x = 1</script></head>"
        '<body><div id="root"></div><script type="module" src="/assets/a.js"></script></body></html>')
    monkeypatch.setattr(seo, "DIST", dist)
    html, hashes = seo.render("/map")
    assert "<!--" not in html
    assert html.count("<title>") == 1 and "<title>El Nino Live Map" in html
    assert "<script>var x = 1</script>" in html  # the theme script survives
    assert '<script type="module" src="/assets/a.js"></script>' in html
    assert html.count('<div id="prerender">') == 1
    assert len(hashes) == 2


def test_no_data_is_said_not_invented():
    r = c.get("/")
    assert r.status_code == 200
    body = r.text.split('<div id="root">', 1)[1]
    assert "ONI (NOAA CPC)</dt><dd>no data yet" in body
    assert "Data updated</dt><dd>n/a" in body
    r = c.get("/samui")
    assert "has not produced an evaluation yet" in r.text


def test_every_route_renders_with_its_own_title():
    seed()
    for path, m in seo.ROUTES.items():
        r = c.get(path)
        assert r.status_code == 200, path
        assert f"<title>{m['title']}</title>" in r.text, path
        assert f'rel="canonical" href="https://elnino.example.org{path}"' in r.text


def test_samui_summary_lists_factors_actions_triggers():
    seed()
    t = c.get("/samui").text
    assert "Level: Prepare" in t
    assert "<td>Water supply</td><td>normal</td><td>103 % of normal</td><td>&lt; 60 %</td>" in t
    assert "Fill the tank." in t and "PWA rationing notice." in t


def test_learn_topic_pages():
    r = c.get("/learn/oni")
    assert r.status_code == 200
    assert "<title>ONI (Oceanic Nino Index): El Nino explained</title>" in r.text
    assert 'rel="canonical" href="https://elnino.example.org/learn/oni"' in r.text
    assert "<h1>ONI (Oceanic Nino Index)</h1>" in r.text
    assert "<li>It uses ERSST.</li>" in r.text  # markdown-lite bullets -> <ul>
    assert "<h2>How to read it</h2>" in r.text
    assert "<th>ONI</th><th>Phase</th>" in r.text
    assert 'href="/learn/roni"' in r.text
    assert 'href="https://www.cpc.ncep.noaa.gov/x" rel="noopener"' in r.text
    # unknown topic: 404 + noindex (no soft-404), still the app shell
    r = c.get("/learn/nope")
    assert r.status_code == 404
    assert 'name="robots" content="noindex,follow' in r.text
    assert '<div id="root">' in r.text
    # the Learn index links to every topic and carries the FAQ text
    t = c.get("/learn").text
    assert 'href="/learn/oni"' in t and 'href="/learn/roni"' in t
    assert "Does El Nino mean no rain on Samui?" in t and "No. It tilts the odds." in t
    assert "Myth: M" in t


def test_redirects():
    for old, new in seo.LEGACY_REDIRECTS.items():
        r = c.get(old, follow_redirects=False)
        assert r.status_code == 301 and r.headers["location"] == new
    r = c.get("/map/", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/map"


# ------------------------------------------------------------------ JSON-LD


def ld_of(html: str) -> dict:
    m = re.search(r'<script type="application/ld\+json" data-path="[^"]*">(.*?)</script>', html,
                  re.DOTALL)
    assert m
    return json.loads(m.group(1))


def test_json_ld_home_graph():
    seed()
    g = ld_of(c.get("/").text)
    assert g["@context"] == "https://schema.org"
    types = {n["@type"]: n for n in g["@graph"]}
    assert types["Organization"]["name"] == "SoClose"
    assert types["WebSite"]["url"] == "https://elnino.example.org/"
    assert types["WebPage"]["url"] == "https://elnino.example.org/"
    assert types["WebPage"]["dateModified"]
    assert types["BreadcrumbList"]["itemListElement"][0]["name"] == "El Nino Watch"
    datasets = [n for n in g["@graph"] if n["@type"] == "Dataset"]
    # every index / Samui weather dataset; page-specific ones (the ERA5 history) live on theirs
    assert len(datasets) == len([d for d in seo.DATASETS if not d.get("page")])
    oni = next(d for d in datasets if d["@id"].endswith("#dataset-oni-roni"))
    assert oni["temporalCoverage"] == "2026-06-15/2026-07-15"
    assert oni["dateModified"] == "2026-07-15"
    assert oni["spatialCoverage"]["geo"]["box"] == "-5 -170 5 -120"
    assert oni["variableMeasured"][0] == {"@type": "PropertyValue", "name": "ONI", "value": 1.8,
                                          "unitText": "degC", "description": "latest value, 2026-07-15"}
    assert oni["distribution"][0]["contentUrl"] == (
        "https://elnino.example.org/api/series?source=cpc_oni&series=oni")
    assert oni["isBasedOn"][0].startswith("https://www.cpc.ncep.noaa.gov/")
    assert oni["license"] and oni["conditionsOfAccess"]
    samui = next(d for d in datasets if d["@id"].endswith("#dataset-samui-weather"))
    assert samui["spatialCoverage"]["geo"]["latitude"] == settings.home_lat
    assert "temporalCoverage" not in samui  # no local rows seeded: nothing claimed
    assert "Place" in types


def test_json_ld_learn_faq_and_topic_article():
    g = ld_of(c.get("/learn").text)
    faq = next(n for n in g["@graph"] if n["@type"] == "FAQPage")
    q = faq["mainEntity"][0]
    assert q["name"] == "Does El Nino mean no rain on Samui?"
    assert q["acceptedAnswer"]["text"] == "No. It tilts the odds."
    g = ld_of(c.get("/learn/oni").text)
    art = next(n for n in g["@graph"] if n["@type"] == "TechArticle")
    assert art["headline"] == "ONI (Oceanic Nino Index)"
    assert art["citation"] == ["https://www.cpc.ncep.noaa.gov/x"]
    assert art["dateModified"] == "2026-09-24"
    crumbs = next(n for n in g["@graph"] if n["@type"] == "BreadcrumbList")["itemListElement"]
    assert [x["name"] for x in crumbs] == ["El Nino Watch", "Learn", "ONI (Oceanic Nino Index)"]


def test_json_ld_is_valid_json_and_escaped():
    seed()
    db.set_status("cpc_alert", {"status": "</script><script>alert(1)</script>", "issued": "2026-09-10"})
    seo.invalidate_caches()
    html = c.get("/").text
    assert "</script><script>alert(1)" not in html
    ld_of(html)  # still parses


# ------------------------------------------------------------------ CSP


def test_csp_allows_injected_scripts_in_public_mode(monkeypatch):
    monkeypatch.setattr(settings, "public_mode", True)
    seed()
    r = c.get("/")
    csp = r.headers["Content-Security-Policy"]
    script_src = next(p for p in csp.split(";") if p.strip().startswith("script-src"))
    html = r.text
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.DOTALL)
    assert len(inline) >= 2  # JSON-LD + route map (+ the theme script of a real build)
    for s in inline:
        assert seo._sha(s) in script_src, "every inline script must be hashed into script-src"
    assert "'unsafe-inline'" not in script_src
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_no_csp_in_local_mode():
    r = c.get("/")
    assert "Content-Security-Policy" not in r.headers


# ------------------------------------------------------------------ robots / sitemap


def test_robots():
    r = c.get("/robots.txt")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    lines = r.text.splitlines()
    assert lines[0] == "User-agent: *" and "Allow: /" in lines
    assert "Disallow: /api/" in lines and "Allow: /api/series" in lines
    assert "Sitemap: https://elnino.example.org/sitemap.xml" in lines


def test_sitemap_lists_routes_and_topics_with_real_lastmod():
    seed()
    r = c.get("/sitemap.xml")
    assert r.status_code == 200 and "xml" in r.headers["content-type"]
    x = r.text
    assert x.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    for p in seo.ROUTES:
        assert f"<loc>https://elnino.example.org{p}</loc>" in x
    assert "<loc>https://elnino.example.org/learn/oni</loc>" in x
    assert "<loc>https://elnino.example.org/learn/roni</loc>" in x
    assert "/learn/nope" not in x
    # lastmod of /samui = local_risk status update (today), of /news = newest feed item
    lm = seo.lastmods()
    assert lm["/samui"] == db.now_iso()[:10]
    assert lm["/news"] == "2026-09-10"
    assert lm["/learn"] >= "2026-09-24"
    assert lm["/indices"] == db.now_iso()[:10]  # newest index run: finished_at is written at insert
    # a route with no data yet has no lastmod tag rather than a fake one
    assert lm["/cams"] is None
    cams_entry = re.search(r"<url><loc>[^<]*/cams</loc>(.*?)</url>", x).group(1)
    assert "<lastmod>" not in cams_entry


# ------------------------------------------------------------------ Open Graph image


def test_og_image_png_cached_and_etag():
    seed()
    r = c.get("/og/current.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert r.headers["Cache-Control"] == "public, max-age=3600"
    etag = r.headers["ETag"]
    assert c.get("/og/current.png", headers={"If-None-Match": etag}).status_code == 304
    from PIL import Image

    assert Image.open(io.BytesIO(r.content)).size == (1200, 630)


def test_og_image_without_data():
    r = c.get("/og/current.png")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"


def test_ascii_fold_keeps_degree_sign():
    assert seo._ascii("El Niño +1.8 °C") == "El Nino +1.8 °C"


# ------------------------------------------------------------------ IndexNow


def test_indexnow_disabled_on_disposable_origin(monkeypatch):
    monkeypatch.setattr(settings, "indexnow_key", "a" * 32)
    monkeypatch.setattr(settings, "public_origin", "https://elnino.203-0-113-10.sslip.io")
    assert not seo.indexnow_enabled()
    monkeypatch.setattr(settings, "public_origin", "https://elnino.soclose.co")
    assert seo.indexnow_enabled()
    monkeypatch.setattr(settings, "indexnow_key", "short")
    assert not seo.indexnow_enabled()
    monkeypatch.setattr(settings, "indexnow_key", "")
    assert not seo.indexnow_enabled()


def test_indexnow_key_file(monkeypatch):
    assert c.get("/abcdefgh12345678.txt").status_code == 404
    monkeypatch.setattr(settings, "indexnow_key", "abcdefgh12345678")
    r = c.get("/abcdefgh12345678.txt")
    assert r.status_code == 200 and r.text == "abcdefgh12345678"
    assert c.get("/robots.txt").status_code == 200  # explicit route still wins


async def test_indexnow_ping_payload(monkeypatch):
    monkeypatch.setattr(settings, "indexnow_key", "k" * 16)
    monkeypatch.setattr(settings, "public_origin", "https://elnino.soclose.co")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx.Response(202)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    out = await seo.indexnow_ping(["https://elnino.soclose.co/", "https://other.org/x"], client)
    assert out == {"sent": 1, "status": 202}
    assert seen["url"] == seo.INDEXNOW_ENDPOINT
    assert seen["json"] == {"host": "elnino.soclose.co", "key": "k" * 16,
                            "keyLocation": "https://elnino.soclose.co/" + "k" * 16 + ".txt",
                            "urlList": ["https://elnino.soclose.co/"]}
    await client.aclose()
    # disabled: nothing sent, no exception
    monkeypatch.setattr(settings, "indexnow_key", "")
    assert (await seo.indexnow_ping(["https://elnino.soclose.co/"]))["sent"] == 0


async def test_post_hook_only_pings_on_change(monkeypatch):
    monkeypatch.setattr(settings, "indexnow_key", "k" * 16)
    monkeypatch.setattr(settings, "public_origin", "https://elnino.soclose.co")
    calls: list[list[str]] = []

    async def fake_ping(urls, client=None):
        calls.append(urls)
        return {"sent": len(urls), "status": 202}

    monkeypatch.setattr(seo, "indexnow_ping", fake_ping)
    seo._last_lastmods = None
    await seo.indexnow_post_hook()   # first run: learns the baseline, pings nothing
    assert calls == []
    await seo.indexnow_post_hook()   # nothing changed
    assert calls == []
    seed()
    await seo.indexnow_post_hook()
    assert calls and "https://elnino.soclose.co/samui" in calls[0]
    assert calls[0][-1] == "https://elnino.soclose.co/sitemap.xml"


# ------------------------------------------------------------------ /history (analogs)


def _seed_history():
    """The 1996-1998 ERA5 fixture + the full CPC ONI / RONI files (real captures, no network)."""
    from app.collectors.indices import parse_oni, parse_roni
    from app.local import analogs as A

    fix = Path(__file__).parent / "fixtures"
    db.upsert_observations("cpc_oni", parse_oni((fix / "indices" / "oni_full.ascii.txt").read_text()))
    db.upsert_observations("cpc_roni", parse_roni((fix / "indices" / "RONI_full.ascii.txt").read_text()))
    mt = A.month_table(json.loads((fix / "local" / "era5_history_1996_1998.json").read_text()))
    db.set_status(A.STATUS_KEY, {"version": A.STATS_VERSION, "months": mt,
                                  "windows": {"1990-1999": {"fetched_at": "x"}, "2000-2009": None},
                                  "first_month": "1996-07", "last_month": "1998-06",
                                  "last_day": "1998-06-30", "point": {"lat": 9.5, "lon": 100.0},
                                  "normals": {}})
    seo.invalidate_caches()


def test_history_page_is_honest_before_the_history_exists():
    r = c.get("/history")
    assert r.status_code == 200
    assert "<title>Past El Ninos on Koh Samui: 1982 to 2024 vs 2026-27</title>" in r.text
    body = r.text.split('<div id="root">', 1)[1]
    assert "No reconstructed event yet" in body
    assert "<td>1997-98</td><td>n/a</td>" in body  # no ONI seeded: n/a, never a number
    assert body.count("n/a") > 20
    assert 'href="/history"' in c.get("/").text  # the nav of every summary links it


def test_history_summary_carries_the_real_numbers_and_the_loading_state():
    seed()
    _seed_history()
    r = c.get("/history")
    body = r.text.split('<div id="root">', 1)[1]
    assert "Loading: 1 decade window(s) of ERA5 data still to fetch (2000-2009)" in body
    assert "<td>1997-98</td><td>+2.37 °C (NDJ 1997)</td><td>+2.28 °C (NDJ 1997)</td><td>very strong El Nino</td>" in body
    assert "<td>39.5 °C (1998-05-01)</td><td>7</td><td>50 d</td>" in body  # from the ERA5 fixture
    assert "<td>1982-83</td><td>+2.14 °C (DJF 1983)</td>" in body and "<td>n/a</td><td>n/a</td><td>n/a</td>" in body
    assert "2026-27 so far</td><td>+1.80 °C (JJA 2026)</td>" in body
    assert "50 days in 1997-98" in body  # takeaway
    assert "documented impacts" in body and 'rel="noopener"' in body
    assert "<h2>Looked for, not found</h2>" in body
    assert "<h2>Method</h2>" in body
    g = ld_of(r.text)
    ds = [n for n in g["@graph"] if n["@type"] == "Dataset"]
    assert len(ds) == 1 and ds[0]["@id"].endswith("#dataset-samui-era5-history")
    assert ds[0]["url"] == "https://elnino.example.org/history"
    crumbs = next(n for n in g["@graph"] if n["@type"] == "BreadcrumbList")
    assert crumbs["itemListElement"][1]["name"] == "Past El Ninos"
    # sitemap: the page is listed and its lastmod is the history document's update time
    assert "<loc>https://elnino.example.org/history</loc>" in c.get("/sitemap.xml").text
    assert seo.lastmods()["/history"] == db.get_status("samui_era5_history")["updated_at"][:10]
