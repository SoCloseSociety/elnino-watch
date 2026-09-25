"""Rules briefing + the optional ComputeForge rewrite (respx, no network)."""

from __future__ import annotations

import os

os.environ.setdefault("SCHEDULER", "false")

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import briefing, db
from app.config import settings

CF = "https://cf.test"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    db.reset_for_tests()
    monkeypatch.setattr(settings, "computeforge_key", "")
    monkeypatch.setattr(settings, "computeforge_url", CF)
    # values below are the ones stored live on 2026-09-24
    db.upsert_observations("cpc_oni", [
        {"series": "oni", "ts": "2026-07-15", "value": 1.8, "meta": {"season": "JJA 2026"}}])
    db.upsert_observations("cpc_weekly_sst", [
        {"series": "nino34_weekly_anom", "ts": "2026-09-16", "value": 3.0}])
    db.set_status("cpc_alert", {"status": "El Niño Advisory", "issued": "2026-09-10",
                                "next_issue": "2026-10-08", "synopsis": "El Niño is "
                                "strengthening.", "url": "https://cpc.example"})
    db.set_status("iri_plume", {"issued": "2026-09-21", "url": "https://iri.example",
                                "probabilities": [
                                    {"season": "SON", "la_nina": 0.0, "neutral": 0.0,
                                     "el_nino": 100.0},
                                    {"season": "MJJ", "la_nina": 2.0, "neutral": 37.0,
                                     "el_nino": 61.0}]})
    db.set_status("local_risk", {
        "level": 2, "level_key": "prepare", "headline": "Prepare.",
        "evaluated_at": "2026-09-24T13:40:45+00:00",
        "factors": [{"id": "enso", "label": "El Nino (event strength)", "level": 2,
                     "level_key": "prepare", "value": 1.8, "unit": "degC",
                     "observed_at": "2026-07-15", "url": "https://cpc.example",
                     "source": "NOAA CPC"},
                    {"id": "air", "label": "Air quality", "level": None}],
        "coverage": {"missing": ["air"], "critical_missing": []},
        "actions": [{"level_key": "prepare", "text": "Fill the cistern."}]})
    db.upsert_events("gdacs", [
        {"ext_id": "TC_1", "category": "cyclone", "title": "Tropical Cyclone ONE-26",
         "severity": "orange", "lat": 18.1, "lon": 83.7, "updated_at": "2026-09-24T10:00:00+00:00"},
        {"ext_id": "FL_1", "category": "flood", "title": "Flood in Malaysia",
         "severity": "green", "lat": 5.0, "lon": 102.0, "updated_at": "2026-09-22T00:00:00+00:00"},
    ])
    db.upsert_feed_items("cpc_discussion", [{"ext_id": "2026-09-10", "kind": "official",
                                             "title": "CPC discussion", "url": "https://c",
                                             "published_at": "2026-09-10"}])


def test_rules_briefing_has_numbers_dates_and_sections():
    d = briefing.build_rules()
    assert d["method"] == "rules" and d["model"] is None
    assert d["headline"] == ("Strong El Nino (ONI +1.80 °C, JJA 2026; Nino 3.4 +3.0 °C week of "
                             f"16 Sep); NOAA CPC: El Niño Advisory (10 Sep). {settings.home_name}: PREPARE.")
    ids = [s["id"] for s in d["sections"]]
    assert ids == ["enso", "forecast", "local", "hazards", "official", "gaps"]
    t = d["text"]
    assert "El Niño Advisory (issued Thu 10 Sep 2026; next update Thu 8 Oct 2026)" in t
    assert "+3.0 °C for the week 13-19 Sep 2026 (centred on Wed 16 Sep, UTC)" in t
    assert "ONI (3-month index, observed): +1.80 °C for JJA 2026 (1 Jun-31 Aug)" in t
    assert "degC" not in t
    assert "SON 100%" in t and "El Nino 61%, neutral 37%, La Nina 2%" in t
    assert "Factors without data: air" in t
    assert "Flood in Malaysia" in t and "km away" in t          # within 800 km
    # a forecast factor is never written as "observed"
    assert "(observed 2026-07-15)" not in t
    assert "ORANGE cyclone: Tropical Cyclone ONE-26" in t        # global major
    assert "2026-09-10: CPC discussion" in t
    assert "\u2014" not in t


def test_unknown_level_is_never_all_clear():
    db.set_status("local_risk", {"level": None, "level_key": "unknown", "headline": "x",
                                 "factors": [], "coverage": {"missing": ["water"],
                                                             "critical_missing": ["water"]}})
    d = briefing.build_rules()
    assert "UNKNOWN (insufficient data)" in d["headline"]
    assert "critical: water" in d["text"]


def test_enso_strength_classes():
    assert briefing.enso_strength(0.3) == "ENSO-neutral"
    assert briefing.enso_strength(1.8) == "strong El Nino"
    assert briefing.enso_strength(2.1) == "very strong El Nino"
    assert briefing.enso_strength(-1.1) == "moderate La Nina"


def _msg(text: str, stop: str = "end_turn") -> dict:
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-fable-5-1",
            "stop_reason": stop,
            "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": text}]}


@respx.mock
async def test_llm_rewrite_used_when_it_adds_no_numbers(monkeypatch):
    monkeypatch.setattr(settings, "computeforge_key", "k")
    route = respx.post(f"{CF}/v1/messages").mock(return_value=httpx.Response(
        200, json=_msg("A strong El Nino is under way: ONI +1.80 degC for JJA 2026.")))
    d = await briefing.refresh(force=True)
    assert d["method"] == "llm" and d["model"] == "claude-fable-5-1"
    assert d["rules_text"].startswith("Strong El Nino")
    req = route.calls[0].request
    assert req.headers["x-api-key"] == "k"
    body = __import__("json").loads(req.content)
    assert body["model"] == settings.briefing_model and "without" not in body["system"].lower()[:0]
    assert "do not add any fact" in body["system"]
    assert db.get_status("briefing")["value"]["method"] == "llm"


@respx.mock
async def test_llm_that_invents_a_number_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "computeforge_key", "k")
    respx.post(f"{CF}/v1/messages").mock(return_value=httpx.Response(
        200, json=_msg("El Nino is strong, ONI +1.80 and rain will fall 40% below normal.")))
    d = await briefing.refresh(force=True)
    assert d["method"] == "rules" and "numbers not in the facts" in d["llm_error"]
    assert "'40'" in d["llm_error"]


@pytest.mark.parametrize("resp,why", [
    (httpx.Response(500, text="upstream down"), "http 500"),
    (httpx.Response(200, json=_msg("", stop="refusal")), "stop_reason refusal"),
    (httpx.Response(200, json=_msg("cut", stop="max_tokens")), "stop_reason max_tokens"),
])
@respx.mock
async def test_llm_failures_fall_back_to_rules(monkeypatch, resp, why):
    monkeypatch.setattr(settings, "computeforge_key", "k")
    respx.post(f"{CF}/v1/messages").mock(return_value=resp)
    d = await briefing.refresh(force=True)
    assert d["method"] == "rules" and why in d["llm_error"]
    assert d["text"].startswith("Strong El Nino")


@respx.mock
async def test_llm_network_error_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "computeforge_key", "k")
    respx.post(f"{CF}/v1/messages").mock(side_effect=httpx.ConnectError("no route"))
    d = await briefing.refresh(force=True)
    assert d["method"] == "rules" and "ConnectError" in d["llm_error"]


async def test_due_every_6h_and_on_level_change():
    await briefing.refresh(force=True)
    assert not briefing.is_due()
    risk = db.get_status("local_risk")["value"]
    db.set_status("local_risk", {**risk, "level": 3, "level_key": "act"})
    assert briefing.is_due()
    await briefing.refresh()
    assert briefing.current()["local_level"] == 3


def test_api_briefing_builds_on_demand():
    from app.main import app

    c = TestClient(app)
    d = c.get("/api/briefing").json()
    assert d["method"] == "rules" and d["sections"] and d["generated_at"]
    assert c.get("/api/status/briefing").json()["value"]["text"] == d["text"]


def test_local_factor_lines_carry_kind_and_validity():
    db.set_status("local_risk", {
        "level": 0, "level_key": "normal", "headline": "Normal.", "headline_local":
        "No immediate threat on Samui: waves max 0.5 m (forecast to Sat 26 Sep).",
        "evaluated_at": "2026-09-24T13:40:45+00:00",
        "factors": [{"id": "heat", "label": "Extreme heat", "level": 0, "level_key": "normal",
                     "value": 37.2, "unit": "degC", "kind": "forecast",
                     "valid_for": "2026-09-30", "observed_at": None,
                     "value_label": "37.2 °C feels-like, forecast for Wed 30 Sep"}],
        "coverage": {"missing": [], "critical_missing": []}, "actions": []})
    d = briefing.build_rules()
    t = d["text"]
    assert ("Extreme heat: NORMAL -- 37.2 °C feels-like, forecast for Wed 30 Sep "
            "[forecast, valid for 2026-09-30].") in t
    assert "observed" not in t.split("Extreme heat")[1].split("\n")[0]
    assert d["headline"].endswith("Koh Samui: NORMAL. No immediate threat on Samui: waves max "
                                  "0.5 m (forecast to Sat 26 Sep).")
