"""Offers per preparedness item and the household budget (pure functions, no network).

Quantities: same rule as the Preparedness page (frontend multiplier()): an item's
`qty` is per "person/day" (x persons x days), per "person" (x persons) or per
"household" (x 1). Children count as persons (same as the page).

Cost of an item: for every listing, packs = ceil(needed / units) and cost = packs x
price; the item's range is the cheapest to the dearest of those. Kits (`components`)
add up each component's cheapest / dearest listing. Items without a usable price are
listed as `unpriced`, never counted as zero.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from urllib.parse import quote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from . import catalog as cat

BKK = ZoneInfo("Asia/Bangkok")
PRIORITIES = ("must", "should", "nice")


def today_bkk() -> date:
    return datetime.now(BKK).date()


def clean_url(url: str) -> str:
    """Percent-encode the path/query (Thai characters, spaces) so every link is valid ASCII."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(p.path, safe="/%-._~"),
                       quote(p.query, safe="=&%+-._~"), p.fragment))


def maps_url(q: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote(q)


def search_url(retailer: str, q: str) -> str:
    return cat.RETAILERS[retailer]["search"].replace("{q}", quote(q, safe=""))


def age_days(checked_at: str, today: date | None = None) -> int:
    return ((today or today_bkk()) - date.fromisoformat(checked_at)).days


def multiplier(per: str | None, adults: int, children: int, days: int) -> int:
    p = re.sub(r"\s", "", (per or "").lower())
    persons = adults + children
    if "person" in p and "day" in p:
        return persons * days
    if "person" in p:
        return persons
    if "day" in p:
        return days
    return 1


# ------------------------------------------------------------------ preparedness items

def prep_items() -> list[dict]:
    """Flattened preparedness items with their category (read live, never copied)."""
    from app.local.preparedness import CATEGORIES

    out = []
    for c in CATEGORIES:
        for it in c["items"]:
            out.append({**it, "category": c["id"], "category_title": c["title"]})
    return out


def coverage(items: list[dict] | None = None) -> dict:
    items = items if items is not None else prep_items()
    prep_ids = [it["id"] for it in items]
    return {"prep_items": len(prep_ids),
            "covered": sum(1 for i in prep_ids if i in cat.ITEM_BY_ID),
            "missing": [i for i in prep_ids if i not in cat.ITEM_BY_ID],
            "unknown": [i for i in cat.ITEM_BY_ID if i not in set(prep_ids)]}


# ------------------------------------------------------------------ offers

def _listing_out(li: dict, today: date) -> dict:
    age = age_days(cat.CHECKED_AT, today)
    unit_price = round(li["price"] / li["units"], 2) if li.get("units") else None
    return {"retailer": li["retailer"],
            "retailer_name": cat.RETAILERS[li["retailer"]]["name"],
            "title": li["title"], "price_thb": li["price"], "units": li.get("units"),
            "unit_price_thb": unit_price, "url": clean_url(li["url"]),
            "source": li.get("source", "retailer"), "checked_at": cat.CHECKED_AT,
            "age_days": age, "recheck": age > cat.STALE_AFTER_DAYS}


def _all_listings(entry: dict) -> list[dict]:
    out = list(entry.get("listings") or [])
    for comp in entry.get("components") or []:
        out.extend(comp["listings"])
    return out


def price_status(entry: dict, today: date | None = None) -> str:
    """ok | recheck (older than STALE_AFTER_DAYS) | unverified (no price) | not_buyable."""
    if not entry.get("buyable"):
        return "not_buyable"
    priced = [li for li in _all_listings(entry) if li.get("price") is not None]
    if not priced:
        return "unverified"
    return "recheck" if age_days(cat.CHECKED_AT, today) > cat.STALE_AFTER_DAYS else "ok"


def offer(entry: dict, prep: dict | None = None, today: date | None = None) -> dict:
    today = today or today_bkk()
    base = {"id": entry["id"], "label": (prep or {}).get("label"),
            "unit": (prep or {}).get("unit"), "priority": (prep or {}).get("priority"),
            "category": (prep or {}).get("category"), "buyable": entry["buyable"],
            "price_status": price_status(entry, today), "checked_at": cat.CHECKED_AT}
    if not entry["buyable"]:
        return {**base, "reason": entry["reason"]}
    links = []
    for r in entry.get("shops", []):
        rt = cat.RETAILERS[r]
        q_en, q_th = entry.get("q_en"), entry.get("q_th")
        qs = [("TH", q_th)] if r in ("globalhouse", "priceza") and q_th else [("EN", q_en)]
        if r in ("lazada", "shopee") and q_th:
            qs.append(("TH", q_th))
        for lang, q in qs:
            if q:
                links.append({"retailer": r, "name": rt["name"], "kind": rt["kind"],
                              "lang": lang, "query": q, "url": search_url(r, q),
                              "hint": rt.get("official_hint")})
    for x in entry.get("extra_links", []):
        links.append({"retailer": None, "name": x["label"], "kind": "official",
                      "lang": None, "query": None, "url": x["url"], "hint": None})
    stores = [{"id": s, **{k: v for k, v in cat.STORES[s].items() if k != "maps_q"},
               "maps_url": maps_url(cat.STORES[s]["maps_q"])} for s in entry.get("local", [])]
    if "boots_central" in entry.get("local", []):
        stores.append({"id": "pharmacy_search", "name": cat.PHARMACY_SEARCH["name"],
                       "area": "Maenam", "address": None, "sells": "Local pharmacies.",
                       "source": None, "maps_url": maps_url(cat.PHARMACY_SEARCH["maps_q"])})
    listings = [_listing_out(li, today) for li in entry.get("listings") or []]
    comps = [{"id": c["id"], "label": c["label"], "count": c["count"],
              "listings": [_listing_out(li, today) for li in c["listings"]]}
             for c in entry.get("components") or []]
    ups = [li["unit_price_thb"] for li in listings if li["unit_price_thb"] is not None]
    return {**base, "spec": entry.get("spec"), "why": entry.get("why"),
            "assumption": entry.get("assumption"), "price_note": entry.get("price_note"),
            "budget_mode": entry.get("budget", "default"),
            "unit_price": ({"min": min(ups), "max": max(ups), "unit": base["unit"]}
                           if ups else None),
            "listings": listings, "components": comps, "search_links": links,
            "local_stores": stores}


def offers(today: date | None = None) -> dict:
    today = today or today_bkk()
    items = prep_items()
    by_id = {it["id"]: it for it in items}
    out = {}
    for entry in cat.ITEMS:
        out[entry["id"]] = offer(entry, by_id.get(entry["id"]), today)
    age = age_days(cat.CHECKED_AT, today)
    return {"checked_at": cat.CHECKED_AT, "age_days": age,
            "stale_after_days": cat.STALE_AFTER_DAYS,
            "recheck": age > cat.STALE_AFTER_DAYS,
            "note": f"Indicative prices, checked on {cat.CHECKED_AT}. Prices change: "
                    "confirm on the shop page before buying.",
            "method": "Curated by hand from retailers' own pages (Makro, HomePro, Global "
                      "House) and, where they had none, Priceza price-comparison listings "
                      "of marketplace sellers. Never scraped at runtime.",
            "retailers": {k: {"name": v["name"], "kind": v["kind"],
                              "hint": v.get("official_hint")}
                          for k, v in cat.RETAILERS.items()},
            "stores": [{"id": k, **{kk: vv for kk, vv in v.items() if kk != "maps_q"},
                        "maps_url": maps_url(v["maps_q"])} for k, v in cat.STORES.items()],
            "references": cat.REFERENCES,
            "coverage": coverage(items), "items": out}


# ------------------------------------------------------------------ budget

def _cost_range(listings: list[dict], needed: float) -> tuple[float, float] | None:
    costs = []
    for li in listings:
        if li.get("price") is None or not li.get("units"):
            continue
        packs = math.ceil(round(needed / li["units"], 9)) if needed > 0 else 0
        costs.append(packs * li["price"])
    return (min(costs), max(costs)) if costs else None


def item_cost(entry: dict, needed: float) -> tuple[float, float] | None:
    if entry.get("components"):
        lo = hi = 0.0
        for comp in entry["components"]:
            r = _cost_range(comp["listings"], comp["count"])
            if r is None:
                return None
            lo, hi = lo + r[0], hi + r[1]
        return lo, hi
    return _cost_range(entry.get("listings") or [], needed)


def _blank() -> dict:
    return {"min": 0.0, "max": 0.0, "priced": 0, "unpriced": []}


def budget(adults: int = 1, children: int = 0, days: int = 14,
           include: tuple[str, ...] = (), today: date | None = None) -> dict:
    """Totals per priority and per category. include: extra budget modes to sum
    ("conditional", "optional")."""
    today = today or today_bkk()
    modes = {"default", *include}
    by_prio = {p: _blank() for p in PRIORITIES}
    by_cat: dict[str, dict] = {}
    rows, excluded, not_buyable, missing = [], [], [], []
    for it in prep_items():
        entry = cat.ITEM_BY_ID.get(it["id"])
        if entry is None:
            missing.append(it["id"])
            continue
        if not entry["buyable"]:
            not_buyable.append(it["id"])
            continue
        mode = entry.get("budget", "default")
        if mode not in modes:
            excluded.append({"id": it["id"], "label": it["label"], "mode": mode,
                             "reason": entry.get("price_note") or mode})
            continue
        qty = it.get("qty") or 0
        needed = qty * multiplier(it.get("per"), adults, children, days)
        cost = item_cost(entry, needed)
        prio = it.get("priority") if it.get("priority") in PRIORITIES else "nice"
        c = by_cat.setdefault(it["category"], {"id": it["category"],
                                               "title": it["category_title"], **_blank()})
        row = {"id": it["id"], "label": it["label"], "category": it["category"],
               "priority": prio, "needed": round(needed, 2), "unit": it.get("unit"),
               "cost_min": None, "cost_max": None,
               "price_status": price_status(entry, today), "note": entry.get("price_note")}
        if cost is None:
            for bucket in (by_prio[prio], c):
                bucket["unpriced"].append(it["id"])
        else:
            row["cost_min"], row["cost_max"] = round(cost[0], 2), round(cost[1], 2)
            for bucket in (by_prio[prio], c):
                bucket["min"] += cost[0]
                bucket["max"] += cost[1]
                bucket["priced"] += 1
        rows.append(row)
    for b in [*by_prio.values(), *by_cat.values()]:
        b["min"], b["max"] = round(b["min"]), round(b["max"])
    age = age_days(cat.CHECKED_AT, today)
    return {"household": {"adults": adults, "children": children, "days": days},
            "currency": "THB", "checked_at": cat.CHECKED_AT, "age_days": age,
            "recheck": age > cat.STALE_AFTER_DAYS,
            "label": f"Indicative, prices checked on {cat.CHECKED_AT}",
            "included_modes": sorted(modes),
            "total": {"min": sum(b["min"] for b in by_prio.values()),
                      "max": sum(b["max"] for b in by_prio.values())},
            "by_priority": by_prio, "by_category": list(by_cat.values()),
            "items": rows, "excluded": excluded, "not_buyable": not_buyable,
            "missing_from_catalog": missing,
            "caveats": ["Delivery, installation and fuel are not included.",
                        "Food uses stated per-day assumptions (see each item).",
                        "Unpriced items are listed, not counted as zero."]}
