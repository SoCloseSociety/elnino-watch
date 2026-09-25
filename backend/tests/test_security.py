"""Public-mode hardening (app/security.py): admin gate, private GETs, docs off,
security headers + CSP, single-flight briefing build, shared /api/layers cache."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os

os.environ.setdefault("SCHEDULER", "false")

import httpx
import pytest
from fastapi.testclient import TestClient

from app import briefing, db, layers_api, security
from app.config import settings
from app.main import app

c = TestClient(app)
TOKEN = "t" * 64


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    db.reset_for_tests()
    security._resp_cache.clear()
    monkeypatch.setattr(settings, "public_mode", False)
    monkeypatch.setattr(settings, "admin_token", "")


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setattr(settings, "public_mode", True)
    monkeypatch.setattr(settings, "admin_token", TOKEN)


ADMIN = {security.ADMIN_HEADER: TOKEN}
PREP = {"checked": {}, "household": {"adults": 2, "children": 0, "days": 14}}


# ------------------------------------------------------------------ local mode


def test_local_mode_unchanged_but_base_headers():
    r = c.put("/api/preparedness/state", json=PREP)
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert r.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "camera=()" in r.headers["Permissions-Policy"]
    assert "Content-Security-Policy" not in r.headers
    assert c.get("/openapi.json").status_code == 200
    assert c.get("/api/access").json() == {"public_mode": False, "admin": False,
                                          "admin_header": "X-Admin-Token"}


# ------------------------------------------------------------------ public mode gate


@pytest.mark.usefixtures("public")
@pytest.mark.parametrize("method,path", [
    ("PUT", "/api/preparedness/state"),
    ("POST", "/api/sources/verify"),
    ("POST", "/api/sources/cpc_oni/run"),
    ("POST", "/api/briefing/refresh"),
    ("POST", "/api/local/evaluate"),
    ("DELETE", "/api/anything"),
    ("PATCH", "/api/"),
])
def test_writes_need_the_admin_token(method, path):
    for headers in ({}, {security.ADMIN_HEADER: "wrong"}, {security.ADMIN_HEADER: ""},
                    {security.ADMIN_HEADER: TOKEN[:-1]}):
        r = c.request(method, path, headers=headers, json=PREP)
        assert r.status_code == 403, (method, path, headers)
        assert "admin only" in r.json()["detail"]
        assert "Content-Security-Policy" in r.headers


@pytest.mark.usefixtures("public")
def test_admin_token_lets_writes_through():
    r = c.put("/api/preparedness/state", json=PREP, headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["household"]["adults"] == 2
    assert c.get("/api/access", headers=ADMIN).json()["admin"] is True


def test_empty_admin_token_means_nobody_is_admin(monkeypatch):
    monkeypatch.setattr(settings, "public_mode", True)
    assert c.put("/api/preparedness/state", json=PREP).status_code == 403
    r = c.put("/api/preparedness/state", json=PREP, headers={security.ADMIN_HEADER: ""})
    assert r.status_code == 403


@pytest.mark.usefixtures("public")
def test_reads_stay_public():
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/sources").status_code == 200
    assert c.options("/api/health").status_code in (200, 405)
    assert c.head("/api/health").status_code in (200, 405)
    assert c.get("/api/access").json()["public_mode"] is True


@pytest.mark.usefixtures("public")
def test_layer_verify_is_admin_only():
    assert c.get("/api/layers/verify").status_code == 403
    assert c.get("/api/layers/verify/?force=true").status_code == 403


@pytest.mark.usefixtures("public")
def test_owner_prep_state_hidden_from_visitors():
    c.put("/api/preparedness/state", json=PREP, headers=ADMIN)
    r = c.get("/api/preparedness/state")
    # 404 = "no server copy": the Prep page falls back to the browser's localStorage
    assert r.status_code == 404
    assert c.get("/api/preparedness/state", headers=ADMIN).json()["household"]["adults"] == 2


@pytest.mark.usefixtures("public")
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_docs_disabled(path):
    assert c.get(path).status_code == 404


# ------------------------------------------------------------------ CSP


def test_csp_hashes_inline_scripts(tmp_path):
    script = "\n      try { document.documentElement.dataset.theme = 'dark' } catch (e) {}\n    "
    index = tmp_path / "index.html"
    index.write_text(f"<html><head><script>{script}</script>"
                     '<script type="module" crossorigin src="/assets/x.js"></script>'
                     "</head></html>")
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = security.content_security_policy(index)
    script_src = next(p for p in csp.split("; ") if p.startswith("script-src "))
    assert script_src == f"script-src 'self' 'sha256-{digest}'"
    assert "'unsafe-eval'" not in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "https://gibs.earthdata.nasa.gov" in csp


@pytest.mark.usefixtures("public")
def test_public_mode_sends_csp_and_hsts_on_https():
    r = c.get("/api/health")
    assert r.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert "Strict-Transport-Security" not in r.headers
    r = TestClient(app, base_url="https://testserver").get("/api/health")
    assert r.headers["Strict-Transport-Security"].startswith("max-age=")


@pytest.mark.skipif(not security.DIST_INDEX.is_file(), reason="frontend not built")
@pytest.mark.usefixtures("public")
def test_index_html_is_no_cache():
    r = c.get("/")
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["Cache-Control"] == "no-cache"
    for h in security.inline_script_hashes():
        assert h in r.headers["Content-Security-Policy"]


# ------------------------------------------------------------------ heavy GETs


@pytest.mark.usefixtures("public")
async def test_briefing_first_build_is_single_flight(monkeypatch):
    calls = 0

    async def fake_refresh(force: bool = False, client=None):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        doc = {"generated_at": "2026-09-24T00:00:00+00:00", "method": "rules", "n": calls}
        db.set_status("briefing", doc)
        return doc

    monkeypatch.setattr(briefing, "refresh", fake_refresh)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
        rs = await asyncio.gather(*(ac.get("/api/briefing") for _ in range(5)))
    assert [r.status_code for r in rs] == [200] * 5
    assert calls == 1
    assert {r.json()["n"] for r in rs} == {1}


@pytest.mark.usefixtures("public")
def test_briefing_served_from_cache(monkeypatch):
    db.set_status("briefing", {"generated_at": "2026-09-24T00:00:00+00:00", "method": "rules"})

    async def boom(*a, **k):
        raise AssertionError("must not rebuild when a briefing exists")

    monkeypatch.setattr(briefing, "refresh", boom)
    assert c.get("/api/briefing").json()["method"] == "rules"


@pytest.mark.usefixtures("public")
def test_layers_catalog_shared_cache(monkeypatch):
    calls = 0

    async def fake_catalog(client):
        nonlocal calls
        calls += 1
        return {"generated_at": "x", "layers": [], "errors": {"gibs_capabilities": "boom"}}

    monkeypatch.setattr(layers_api, "build_catalog", fake_catalog)
    a, b = c.get("/api/layers"), c.get("/api/layers")
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert calls == 1
    assert a.headers["content-type"].startswith("application/json")
    assert "Content-Security-Policy" in b.headers


@pytest.mark.skipif(not security.DIST_INDEX.is_file(), reason="frontend not built")
def test_head_on_spa_routes():
    for path in ("/", "/map", "/prep"):
        r = c.head(path)
        assert r.status_code == 200, path
        assert r.headers["content-type"].startswith("text/html")
        assert r.content == b""
