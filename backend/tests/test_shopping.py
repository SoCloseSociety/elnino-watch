"""Shopping panel: curated catalog integrity, budget maths, freshness, API (no network)."""

from __future__ import annotations

import os

os.environ.setdefault("SCHEDULER", "false")

import re
from datetime import date, timedelta
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.shopping import api, catalog, offers

CHECKED = date.fromisoformat(catalog.CHECKED_AT)
ALLOWED_LISTING_HOSTS = {"www.makro.pro", "www.homepro.co.th", "www.globalhouse.co.th",
                         "www.priceza.com"}
TEXT_FIELDS = ("spec", "why", "assumption", "price_note", "reason")


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def all_listings(entry: dict) -> list[dict]:
    out = list(entry.get("listings") or [])
    for c in entry.get("components") or []:
        out += c["listings"]
    return out


# ------------------------------------------------------------------ catalog integrity

def test_every_preparedness_item_has_a_shopping_entry():
    cov = offers.coverage()
    assert cov["missing"] == [], (
        f"add these ids to app/shopping/catalog.py ITEMS (buyable or _no(...)): "
        f"{cov['missing']}")
    assert cov["unknown"] == [], f"catalog ids no longer in preparedness: {cov['unknown']}"


def test_ids_unique():
    ids = [e["id"] for e in catalog.ITEMS]
    assert len(ids) == len(set(ids))


def test_buyable_entries_are_complete():
    for e in catalog.ITEMS:
        if not e["buyable"]:
            assert e["reason"], e["id"]
            assert not e.get("listings") and not e.get("shops"), e["id"]
            continue
        assert e.get("spec") and e.get("why"), f"{e['id']}: spec + why required"
        assert e.get("q_en"), e["id"]
        assert set(e.get("shops", [])) <= set(catalog.RETAILERS), e["id"]
        assert set(e.get("local", [])) <= set(catalog.STORES), e["id"]
        assert e.get("budget", "default") in ("default", "conditional", "optional")
        if not all_listings(e):
            assert e.get("price_note"), f"{e['id']}: unpriced item must say why"


def test_listings_are_real_urls_with_positive_prices():
    for e in catalog.ITEMS:
        for li in all_listings(e):
            assert li["retailer"] in catalog.RETAILERS
            assert li["source"] in ("retailer", "marketplace")
            assert li["price"] is None or li["price"] > 0, (e["id"], li)
            assert li["units"] is None or li["units"] > 0, (e["id"], li)
            url = offers.clean_url(li["url"])
            parts = urlsplit(url)
            assert parts.scheme == "https" and parts.netloc in ALLOWED_LISTING_HOSTS, url
            assert url.isascii() and " " not in url, url
            if li["source"] == "marketplace":
                assert li["retailer"] == "priceza", "marketplace prices come via Priceza"


def test_stores_have_a_source_and_maps_search():
    for sid, s in catalog.STORES.items():
        assert s["source"].startswith("https://"), sid
        assert s["maps_q"], sid
        assert offers.maps_url(s["maps_q"]).startswith(
            "https://www.google.com/maps/search/?api=1&query=")


def test_text_is_english_ascii_without_em_dash():
    for e in catalog.ITEMS:
        for f in TEXT_FIELDS:
            v = e.get(f)
            if not v:
                continue
            assert "—" not in v and "–" not in v, (e["id"], f)
            # Thai is allowed only inside parentheses (the local name shoppers look for)
            stripped = re.sub(r"\([^)]*\)", "", v)
            assert stripped.isascii(), (e["id"], f, v)
        for li in all_listings(e):
            assert li["title"].isascii() or "(" in li["title"], (e["id"], li["title"])


def test_search_links_encode_thai_and_cover_marketplaces():
    o = offers.offer(catalog.ITEM_BY_ID["water_jerrycans"])
    urls = [x["url"] for x in o["search_links"]]
    assert all(u.isascii() for u in urls)
    names = {(x["retailer"], x["lang"]) for x in o["search_links"]}
    assert {("lazada", "EN"), ("lazada", "TH"), ("shopee", "EN"), ("shopee", "TH"),
            ("globalhouse", "TH")} <= names
    assert any(u.startswith("https://www.lazada.co.th/catalog/?q=") for u in urls)
    assert any(u.startswith("https://shopee.co.th/search?keyword=") for u in urls)


def test_not_buyable_items_get_no_links():
    o = offers.offer(catalog.ITEM_BY_ID["doc_passport"])
    assert o["buyable"] is False and "search_links" not in o and o["reason"]
    assert o["price_status"] == "not_buyable"


# ------------------------------------------------------------------ budget maths

def test_multiplier_matches_prep_page_rule():
    assert offers.multiplier("person/day", 2, 1, 14) == 42
    assert offers.multiplier("person", 2, 1, 14) == 3
    assert offers.multiplier("household", 2, 1, 14) == 1
    assert offers.multiplier(None, 2, 1, 14) == 1


def test_cost_rounds_up_to_whole_packs():
    entry = {"id": "x", "buyable": True, "listings": [
        catalog.L("makro", "6 L", 35, 6, "https://www.makro.pro/en/p/a"),
        catalog.L("makro", "9 L", 49, 9, "https://www.makro.pro/en/p/b")]}
    # 20 L: 4 x 6 L = 140, 3 x 9 L = 147
    assert offers.item_cost(entry, 20) == (140, 147)
    assert offers.item_cost(entry, 0) == (0, 0)
    assert offers.item_cost({"listings": []}, 5) is None
    unconvertible = {"listings": [catalog.L("makro", "tin", 460, None, "https://x/")]}
    assert offers.item_cost(unconvertible, 5) is None


def test_components_add_up():
    e = catalog.ITEM_BY_ID["power_solar"]
    lo, hi = offers.item_cost(e, 1)
    st = [li["price"] for li in e["components"][0]["listings"]]
    pn = [li["price"] for li in e["components"][1]["listings"]]
    assert (lo, hi) == (min(st) + min(pn), max(st) + max(pn))


def test_budget_totals_are_consistent():
    b = offers.budget(2, 0, 14, today=CHECKED)
    rows = [r for r in b["items"] if r["cost_min"] is not None]
    for p in offers.PRIORITIES:
        pr = [r for r in rows if r["priority"] == p]
        assert b["by_priority"][p]["priced"] == len(pr)
        assert abs(b["by_priority"][p]["min"] - sum(r["cost_min"] for r in pr)) <= 1
        assert abs(b["by_priority"][p]["max"] - sum(r["cost_max"] for r in pr)) <= 1
    assert b["total"]["min"] == sum(v["min"] for v in b["by_priority"].values())
    assert b["total"]["min"] <= b["total"]["max"]
    assert abs(sum(c["min"] for c in b["by_category"]) - b["total"]["min"]) <= len(b["by_category"])
    assert b["label"] == f"Indicative, prices checked on {catalog.CHECKED_AT}"
    # unpriced items are listed, never counted as zero
    unpriced = [r["id"] for r in b["items"] if r["cost_min"] is None]
    listed = [i for v in b["by_priority"].values() for i in v["unpriced"]]
    assert sorted(unpriced) == sorted(listed)
    assert "health_ors" in listed


def test_budget_scales_with_household_and_days():
    small = offers.budget(1, 0, 7, today=CHECKED)
    big = offers.budget(4, 2, 30, today=CHECKED)
    assert big["total"]["min"] > small["total"]["min"]
    w = next(r for r in big["items"] if r["id"] == "water_drink")
    assert w["needed"] == 4 * 6 * 30  # 4 L/person/day


def test_conditional_and_optional_only_when_asked():
    base = offers.budget(2, 0, 14, today=CHECKED)
    ids = {r["id"] for r in base["items"]}
    assert "water_tank" not in ids and "pet_carrier" not in ids
    assert {"water_tank", "pet_carrier", "food_baby", "pet_food"} <= {
        e["id"] for e in base["excluded"]}
    full = offers.budget(2, 0, 14, include=("conditional", "optional"), today=CHECKED)
    assert full["total"]["min"] > base["total"]["min"]
    baby = next(r for r in full["items"] if r["id"] == "food_baby")
    assert baby["cost_min"] is None  # tins cannot be converted to days: not guessed


# ------------------------------------------------------------------ freshness

def test_prices_flagged_recheck_after_60_days():
    fresh = offers.offers(today=CHECKED + timedelta(days=catalog.STALE_AFTER_DAYS))
    assert fresh["recheck"] is False
    assert fresh["items"]["water_drink"]["price_status"] == "ok"
    old = offers.offers(today=CHECKED + timedelta(days=catalog.STALE_AFTER_DAYS + 1))
    assert old["recheck"] is True
    assert old["items"]["water_drink"]["price_status"] == "recheck"
    assert all(li["recheck"] for li in old["items"]["water_drink"]["listings"])
    assert old["items"]["water_tablets"]["price_status"] == "unverified"


# ------------------------------------------------------------------ API

def test_api_shopping(client):
    r = client.get("/api/shopping")
    assert r.status_code == 200
    j = r.json()
    assert j["checked_at"] == catalog.CHECKED_AT
    assert j["coverage"]["missing"] == []
    w = j["items"]["water_drink"]
    assert w["label"] and w["priority"] == "must" and w["listings"]
    assert w["unit_price"]["min"] <= w["unit_price"]["max"]
    assert any(s["id"] == "makro_samui" for s in w["local_stores"])


def test_api_budget(client):
    r = client.get("/api/shopping/budget", params={"adults": 2, "children": 0, "days": 14})
    assert r.status_code == 200
    j = r.json()
    assert j["household"] == {"adults": 2, "children": 0, "days": 14}
    assert set(j["by_priority"]) == {"must", "should", "nice"}
    r2 = client.get("/api/shopping/budget", params=[("adults", 2), ("include", "optional")])
    assert r2.status_code == 200 and "optional" in r2.json()["included_modes"]
    assert client.get("/api/shopping/budget", params={"adults": 0}).status_code == 422
    assert client.get("/api/shopping/budget", params={"days": 500}).status_code == 422
    assert client.get("/api/shopping/budget", params={"include": "x"}).status_code == 422


def test_api_item(client):
    assert client.get("/api/shopping/haze_masks").json()["spec"]
    assert client.get("/api/shopping/nope").status_code == 404
