"""Alert planning / delivery and the local HTTP routes."""

from __future__ import annotations

import json
import os

os.environ.setdefault("SCHEDULER", "false")

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.local import alerts


@pytest.fixture(autouse=True)
def mem_db(monkeypatch):
    db.reset_for_tests()
    for k in ("telegram_bot_token", "telegram_chat_id", "neo_api_url", "neo_api_token"):
        monkeypatch.setattr(settings, k, "")


def fake_risk(level: int, factors=None) -> dict:
    keys = ["normal", "vigilance", "prepare", "act", "leave"]
    return {"level": level, "level_key": keys[level], "level_label": keys[level],
            "headline": f"level {level}", "factors": factors or []}


def test_plan_only_on_rise_or_factor_three():
    assert alerts.plan_alerts(fake_risk(2), previous_level=2) == []
    assert alerts.plan_alerts(fake_risk(1), previous_level=2) == []
    rise = alerts.plan_alerts(fake_risk(2), previous_level=1)
    assert rise[0]["kind"] == "local_level" and rise[0]["dedup_key"].startswith("local_level:prepare:")
    fac = {"id": "flood", "label": "Inondation", "level": 3, "level_key": "act", "value": 120,
           "unit": "mm", "explanation": "x"}
    planned = alerts.plan_alerts(fake_risk(3, [fac]), previous_level=3)
    assert [a["kind"] for a in planned] == ["factor_flood"]


async def test_dispatch_stores_without_channels_and_dedups():
    r = fake_risk(3)
    created = await alerts.dispatch(r, previous_level=0)
    assert len(created) == 1 and created[0]["delivered"] == []
    assert await alerts.dispatch(r, previous_level=0) == []  # same day, same level
    row = db.query("SELECT * FROM alerts")[0]
    assert row["level"] == "act" and json.loads(row["delivered"]) == []


@respx.mock
async def test_dispatch_delivers_telegram_and_neo(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "TKN")
    monkeypatch.setattr(settings, "telegram_chat_id", "42")
    monkeypatch.setattr(settings, "neo_api_url", "http://neo.test:8888/")
    monkeypatch.setattr(settings, "neo_api_token", "SECRET")
    tg = respx.post("https://api.telegram.org/botTKN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True}))
    neo = respx.post("http://neo.test:8888/device_alert").mock(
        return_value=httpx.Response(500))
    created = await alerts.dispatch(fake_risk(4), previous_level=2)
    assert created[0]["delivered"] == ["telegram", "neo:error"]
    assert json.loads(tg.calls[0].request.content)["chat_id"] == "42"
    req = neo.calls[0].request
    body = json.loads(req.content)
    assert req.headers["Authorization"] == "Bearer SECRET"
    assert body["device"] == "elnino-watch" and body["kind"] == "elnino"
    assert len(body["highs"]) <= 300
    assert json.loads(db.query("SELECT delivered FROM alerts")[0]["delivered"]) == [
        "telegram", "neo:error"]


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def test_api_local_on_empty_db(client):
    r = client.get("/api/local")
    assert r.status_code == 200
    body = r.json()
    for k in ("level", "level_key", "headline", "evaluated_at", "home", "factors", "actions",
              "triggers"):
        assert k in body
    for fct in body["factors"]:
        assert {"id", "label", "level", "level_key", "value", "unit", "threshold",
                "explanation", "source", "url", "observed_at"} <= set(fct)
    assert client.get("/api/local/history").json()[-1]["level"] == body["level"]


def test_api_weather_shape(client):
    w = client.get("/api/local/weather").json()
    assert len(w["days"]) == 92 + 15 + 1
    assert w["days"][-1]["forecast"] and not w["days"][0]["forecast"]


def test_api_preparedness_and_state(client):
    p = client.get("/api/preparedness").json()
    ids = [it["id"] for c in p["categories"] for it in c["items"]]
    assert len(ids) == len(set(ids))
    for c in p["categories"]:
        for it in c["items"]:
            assert it["priority"] in ("must", "should", "nice")
            assert it["per"] in ("person/day", "person", "household")
    assert {s["id"] for s in p["scenarios"]} >= {"drought", "heatwave", "storm_flood", "haze",
                                                  "isolation"}
    nums = {c["number"] for c in p["contacts"]}
    assert {"191", "1669", "199", "1155", "1784"} <= nums
    assert all(c.get("source") or c.get("url") or c["id"] == "embassy" for c in p["contacts"])
    assert client.get("/api/preparedness/state").json()["household"]["days"] == 14
    put = client.put("/api/preparedness/state",
                     json={"checked": {"water_drink": True, "food_opener": False},
                           "household": {"adults": 2, "children": 1, "days": 21}})
    assert put.status_code == 200
    st = client.get("/api/preparedness/state").json()
    assert st == {"checked": {"water_drink": True},
                  "household": {"adults": 2, "children": 1, "days": 21}}
    bad = client.put("/api/preparedness/state", json={"checked": {"nope": True}})
    assert bad.status_code == 422


def test_no_em_dashes_in_local_text():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app" / "local"
    for p in root.glob("*.py"):
        assert "—" not in p.read_text(encoding="utf-8"), p
