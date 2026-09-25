"""Exit plan for Koh Samui: can I leave, when, how, and what to do before leaving.

GET /api/local/exit ->
  {recommendation, level, level_key, evaluated_at,
   signals: [{id, label, status: ok|caution|blocked|unknown, value, unit, unit_label,
              threshold, reason, source, url, kind, valid_for, retrieved_at, as_of,
              observed_at}],     # observed_at is null for forecasts (see provenance.py)
   windows: [{date, ok, status, reason, wave_max_m, gust_max_kmh}],   # next 7 local days
   routes: [{id, mode: ferry|air|rail, operator, from, to, url, notes}],
   checklist: [{id, label, priority}], verified_at, notes}

Thresholds (documented, see each constant):
- Waves (Open-Meteo Marine daily max significant height, open water east of Samui):
  >= 2 m caution (TMD advises small boats to stay ashore in 2-3 m seas; high-speed
  catamarans are the first cancelled), >= 3 m blocked (car ferries likely suspended).
- TMD bulletins for the Gulf: a wave warning = caution; "small boats should stay
  ashore" = blocked for small / fast boats (so blocked for leaving by boat).
- Wind gusts (Open-Meteo daily max, island point): >= 62 km/h caution (Beaufort 8, gale;
  45-60 km/h gusts are routine in both monsoons and ferries run), >= 75 km/h blocked
  (Beaufort 9, strong gale).
- Tropical cyclone (GDACS / EONET events): any within 800 km caution, within 300 km or
  orange/red within 800 km blocked (the sea closes before the storm arrives).
- Heavy rain: a TMD heavy-rain bulletin for the South/Gulf or >= 90 mm/24 h forecast
  caution (roads to piers and on the mainland), >= 150 mm/24 h blocked.
Missing or stale data is `unknown`, never `ok`.

Routes: only operators whose official website answered HTTP 200 on 2026-09-24
(`python -m app.local.exit --verify` re-checks them). No schedules or prices: they
change; each route says what to check and where.
"""

from __future__ import annotations

from datetime import date, timedelta

from .. import db
from ..config import settings
from . import provenance as P
from . import risk
from .collectors import today_bkk
from .provenance import fmt_day, interval

WAVE_CAUTION_M = 2.0
WAVE_BLOCKED_M = 3.0
GUST_CAUTION_KMH = 62.0   # Beaufort 8; daily max gusts of 45-60 km/h are routine
GUST_BLOCKED_KMH = 75.0
CYCLONE_WATCH_KM = 800.0
CYCLONE_CLOSE_KM = 300.0
RAIN_CAUTION_MM = 90.0     # TMD "very heavy" > 90 mm/24 h
RAIN_BLOCKED_MM = 150.0
RANK = {"ok": 0, "unknown": 1, "caution": 2, "blocked": 3}

VERIFIED_AT = "2026-09-24"
ROUTES = [
    {"id": "seatran", "mode": "ferry", "operator": "Seatran Ferry",
     "from": "Samui, Nathon (Seatran pier)", "to": "Donsak pier (Surat Thani)",
     "url": "https://www.seatranferry.com/",
     "notes": ("Car and passenger ferry. Check that day's departures and any weather "
               "cancellation on the operator's site or at the pier; vehicles queue early "
               "when the sea is about to close.")},
    {"id": "raja", "mode": "ferry", "operator": "Raja Ferry",
     "from": "Samui, Lipa Noi pier", "to": "Donsak pier (Surat Thani)",
     "url": "https://www.rajaferryport.com/",
     "notes": ("Car and passenger ferry. Check departures and cancellations on the operator's "
               "site; it is the other car-ferry line if Seatran is full.")},
    {"id": "lomprayah_donsak", "mode": "ferry", "operator": "Lomprayah",
     "from": "Samui (pier shown on the ticket)", "to": "Donsak / Surat Thani (boat + bus)",
     "url": "https://www.lomprayah.com/",
     "notes": ("Passenger service. Check the pier and whether the sea crossing runs that "
               "day on the operator's site.")},
    {"id": "lomprayah_chumphon", "mode": "ferry", "operator": "Lomprayah",
     "from": "Samui, Maenam (Pralarn) or Bangrak pier", "to": "Chumphon (via Koh Phangan, "
     "Koh Tao)",
     "url": "https://www.lomprayah.com/",
     "notes": ("High-speed catamaran across the open Gulf: the most exposed route and the "
               "first cancelled in rough seas, especially in the northeast monsoon. "
               "Chumphon has trains and buses to Bangkok.")},
    {"id": "usm", "mode": "air", "operator": "Samui International Airport (USM)",
     "from": "Samui International Airport (USM)", "to": "Bangkok and other airports",
     "url": "https://www.samuiairport.com/",
     "notes": ("The airport site is run by Bangkok Airport Management Co. Bangkok Airways "
               "operates most flights (its site blocks automated checks, so it is not "
               "linked here: open bangkokair.com in a browser). Limited seats and high "
               "fares when everyone leaves; flights can also be cancelled in a storm.")},
    {"id": "thai_usm", "mode": "air", "operator": "Thai Airways",
     "from": "Samui (USM)", "to": "Bangkok",
     "url": "https://www.thaiairways.com/flights/en/flights-to-ko-samui",
     "notes": "Check on its site whether the flight is its own or a codeshare, and seats."},
    {"id": "urt", "mode": "air", "operator": "Surat Thani Airport (URT, Department of "
     "Airports)", "from": "Surat Thani (mainland, after the ferry)", "to": "Bangkok",
     "url": "https://minisite.airports.go.th/suratthani",
     "notes": ("More airlines and seats than Samui (e.g. Nok Air https://www.nokair.com/, "
               "AirAsia https://www.airasia.com/): useful when USM is full or too "
               "expensive. Check flights on the airlines' sites.")},
    {"id": "srt", "mode": "rail", "operator": "State Railway of Thailand",
     "from": "Surat Thani railway station (Phun Phin, mainland)", "to": "Bangkok and the "
     "national network", "url": "https://www.railway.co.th/",
     "notes": ("Tickets: https://dticket.railway.co.th/ . Southern-line floods can cut the "
               "line in the northeast monsoon: check before relying on it.")},
]

CHECKLIST = [
    {"id": "docs", "label": "Passport, visa / extension papers, insurance policy + hotline, "
     "copies in a dry bag and online", "priority": "must"},
    {"id": "money", "label": "Cash in baht (ATMs empty fast) + two cards from different "
     "banks", "priority": "must"},
    {"id": "meds", "label": "Prescription medication for 30 days + prescriptions",
     "priority": "must"},
    {"id": "booking", "label": "Confirm the crossing on the day (operator site or pier); a "
     "flexible ticket; a place to stay on the mainland", "priority": "must"},
    {"id": "tell", "label": "Tell someone off the island your route and times",
     "priority": "must"},
    {"id": "power", "label": "Phone + power banks charged, offline maps of Samui and Surat "
     "Thani, emergency numbers written down", "priority": "must"},
    {"id": "gobag", "label": "Go-bag: 1 day of water and food, clothes, headlamp, "
     "rain gear", "priority": "must"},
    {"id": "pets", "label": "Pets: carrier, vaccination record, food; check the ferry or "
     "airline rules for animals before going to the pier", "priority": "should"},
    {"id": "fuel", "label": "Vehicle fuelled (car ferries queue for hours)",
     "priority": "should"},
    {"id": "home_water", "label": "Home: close the main water valve, cover the tank "
     "(mosquitoes), turn off the pump", "priority": "should"},
    {"id": "home_power", "label": "Home: main breaker off (or leave only the fridge "
     "circuit), unplug electronics, gas bottle closed", "priority": "should"},
    {"id": "home_windows", "label": "Home: windows and shutters closed, outdoor items "
     "tied down or brought in", "priority": "should"},
    {"id": "home_high", "label": "Home: valuables, documents and electronics up high "
     "(flooding), fridge emptied if the power may be cut for long", "priority": "should"},
    {"id": "authorities", "label": "Follow official instructions: DDPM 1784, TMD 1182",
     "priority": "must"},
]


def _sig(id_: str, label: str, status: str, value=None, unit: str | None = None,
         threshold: str = "", source: str = "", url: str = "",
         observed_at: str | None = None, reason: str = "", *, kind: str | None = None,
         valid_for: str | None = None, retrieved: str | None = None) -> dict:
    if kind == "forecast":
        observed_at = None  # a forecast is never "observed"
    return {"id": id_, "label": label, "status": status, "value": value, "unit": unit,
            "unit_label": P.unit_label(unit), "threshold": threshold, "reason": reason,
            "source": source, "url": url, "kind": kind, "valid_for": valid_for,
            "retrieved_at": retrieved, "as_of": observed_at or retrieved,
            "observed_at": observed_at}


def _grade(v: float, caution: float, blocked: float) -> str:
    return "blocked" if v >= blocked else "caution" if v >= caution else "ok"


def _daily(series: str, start: date, days: int, source: str | None = None) -> dict[str, float]:
    pts = risk._points(series, start.isoformat(), (start + timedelta(days=days)).isoformat(),
                       source)
    out: dict[str, float] = {}
    for p in pts:
        d = p["ts"][:10]
        out[d] = max(out.get(d, p["value"]), p["value"])
    return out


def sea_signal(today: date) -> dict:
    th = f">= {WAVE_CAUTION_M:g} m caution, >= {WAVE_BLOCKED_M:g} m blocked (today + 2 days)"
    waves = _daily("samui_wave_height", today, 3)
    lab = "Waves (ferry crossing)"
    if not waves or risk._stale("openmeteo_marine", 24 * 3600):
        return _sig("waves", lab, "unknown", threshold=th, source="Open-Meteo Marine",
                    url=risk.URLS["marine"], reason="no current wave forecast")
    d, v = max(waves.items(), key=lambda kv: kv[1])
    return _sig("waves", lab, _grade(v, WAVE_CAUTION_M, WAVE_BLOCKED_M), round(v, 1), "m",
                th, "Open-Meteo Marine", risk.URLS["marine"], None,
                f"forecast max {v:.1f} m on {fmt_day(d)}", kind="forecast", valid_for=d,
                retrieved=P.retrieved_at("openmeteo_marine"))


def tmd_sea_signal() -> dict:
    th = "Gulf wave warning caution; 'small boats should stay ashore' blocked"
    lab = "TMD sea warnings (Gulf)"
    tmd = db.get_status("tmd_warnings")
    if not tmd or risk._stale("tmd_warnings", 6 * 3600):
        return _sig("tmd_sea", lab, "unknown", threshold=th, source="TMD",
                    url=risk.URLS["tmd"], reason="TMD bulletins not received recently")
    warns = risk.tmd_gulf_wave_warnings()
    obs = P.retrieved_at("tmd_warnings") or tmd["updated_at"]
    if not warns:
        return _sig("tmd_sea", lab, "ok", None, None, th, "TMD", risk.URLS["tmd_warn"], None,
                    "no TMD wave warning for the Gulf in force", kind="bulletin",
                    retrieved=obs)
    w = warns[0]
    boats = any(x.get("small_boats_ashore") for x in warns)
    hm = max((x.get("wave_m_max") or 0) for x in warns) or None
    status = "blocked" if boats or (hm and hm >= WAVE_BLOCKED_M) else "caution"
    return _sig("tmd_sea", lab, status, hm, "m" if hm else None, th, "TMD",
                risk.URLS["tmd_warn"], None,
                f"{risk.tmd_text(w)}, in force until {fmt_day(w['until'])}"
                + (": small boats should stay ashore" if boats else ""), kind="bulletin",
                valid_for=interval(w.get("from") or w["until"], w["until"]), retrieved=obs)


def gust_signal(today: date) -> dict:
    th = (f">= {GUST_CAUTION_KMH:g} km/h caution, >= {GUST_BLOCKED_KMH:g} km/h blocked "
          "(today + 2 days)")
    lab = "Wind gusts"
    g = _daily("samui_wind_gust_max", today, 3, "openmeteo_samui")
    if not g or risk._stale("openmeteo_samui", 36 * 3600):
        return _sig("gusts", lab, "unknown", threshold=th, source="Open-Meteo",
                    url=risk.URLS["forecast"], reason="no current wind forecast")
    d, v = max(g.items(), key=lambda kv: kv[1])
    return _sig("gusts", lab, _grade(v, GUST_CAUTION_KMH, GUST_BLOCKED_KMH), round(v),
                "km/h", th, "Open-Meteo", risk.URLS["forecast"], None,
                f"forecast max {v:.0f} km/h on {fmt_day(d)}", kind="forecast", valid_for=d,
                retrieved=P.retrieved_at("openmeteo_samui"))


def cyclone_signal() -> dict:
    th = (f"any cyclone <= {CYCLONE_WATCH_KM:.0f} km caution; <= {CYCLONE_CLOSE_KM:.0f} km "
          f"or orange/red <= {CYCLONE_WATCH_KM:.0f} km blocked")
    lab = "Tropical cyclone nearby"
    fresh = not risk._stale("gdacs%", 3 * 3600) or not risk._stale("eonet", 6 * 3600)
    evs = []
    for e in db.query("SELECT source, title, url, severity, lat, lon, updated_at FROM events "
                      "WHERE category='cyclone' AND lat IS NOT NULL"):
        e["distance_km"] = round(risk.haversine_km(settings.home_lat, settings.home_lon,
                                                   e["lat"], e["lon"]))
        evs.append(e)
    near = sorted([e for e in evs if e["distance_km"] <= CYCLONE_WATCH_KM],
                  key=lambda e: e["distance_km"])
    if not near:
        if not fresh:
            return _sig("cyclone", lab, "unknown", threshold=th, source="GDACS / EONET",
                        url=risk.URLS["gdacs"], reason="cyclone feeds not received recently")
        nearest = min(evs, key=lambda e: (e["distance_km"], risk.SOURCE_RANK.get(
            e.get("source"), 9))) if evs else None
        extra = (f" (nearest: {nearest['title']}, {nearest['distance_km']:,} km)"
                 if nearest else "")
        return _sig("cyclone", lab, "ok", None, "km", th, "GDACS / EONET", risk.URLS["gdacs"],
                    None, f"no cyclone within {CYCLONE_WATCH_KM:,.0f} km{extra}",
                    kind="bulletin", retrieved=P.retrieved_at("gdacs"))
    e = near[0]
    big = any((x.get("severity") or "").lower() in ("orange", "red") for x in near)
    status = "blocked" if e["distance_km"] <= CYCLONE_CLOSE_KM or big else "caution"
    return _sig("cyclone", lab, status, e["distance_km"], "km", th, "GDACS / EONET",
                e.get("url") or risk.URLS["gdacs"], e.get("updated_at"),
                f"{e['title']} ({e.get('severity')}) at {e['distance_km']:,} km",
                kind="bulletin", valid_for=(e.get("updated_at") or "")[:10] or None,
                retrieved=P.retrieved_at("gdacs"))


def rain_signal(today: date) -> dict:
    th = (f"TMD heavy-rain bulletin or >= {RAIN_CAUTION_MM:g} mm/24 h caution, "
          f">= {RAIN_BLOCKED_MM:g} mm/24 h blocked")
    lab = "Heavy rain (roads to the piers, mainland)"
    r = _daily("samui_precip", today, 3, "openmeteo_samui")
    warns = risk._tmd_active(lambda it: it.get("heavy_rain"))
    if not r or risk._stale("openmeteo_samui", 36 * 3600):
        if warns:
            w = warns[0]
            return _sig("rain", lab, "caution", None, None, th, "TMD", risk.URLS["tmd_warn"],
                        None, f"{risk.tmd_text(w)} (no rain forecast data)", kind="bulletin",
                        valid_for=interval(w.get("from") or w["until"], w["until"]),
                        retrieved=P.retrieved_at("tmd_warnings"))
        return _sig("rain", lab, "unknown", threshold=th, source="Open-Meteo / TMD",
                    url=risk.URLS["forecast"], reason="no current rain forecast")
    d, v = max(r.items(), key=lambda kv: kv[1])
    status = _grade(v, RAIN_CAUTION_MM, RAIN_BLOCKED_MM)
    reason = f"forecast wettest day {fmt_day(d)}: {v:.0f} mm"
    if warns:
        reason += (f"; {risk.tmd_text(warns[0])}, in force until "
                   f"{fmt_day(warns[0]['until'])}")
        status = max(status, "caution", key=RANK.get)
    return _sig("rain", lab, status, round(v), "mm", th, "Open-Meteo, TMD",
                risk.URLS["forecast"], None, reason, kind="forecast", valid_for=d,
                retrieved=P.retrieved_at("openmeteo_samui"))


def windows(today: date, cyc: dict, n: int = 7) -> list[dict]:
    """Per local day: can one leave by ferry? Waves and gusts of that day, TMD Gulf wave
    bulletins until their end date, a nearby cyclone for the first 3 days."""
    waves = _daily("samui_wave_height", today, n)
    gusts = _daily("samui_wind_gust_max", today, n, "openmeteo_samui")
    tmd = risk.tmd_gulf_wave_warnings()
    out = []
    for i in range(n):
        d = (today + timedelta(days=i)).isoformat()
        w, g = waves.get(d), gusts.get(d)
        status, why = "ok", []
        if w is None:
            status = "unknown"
            why.append("no wave forecast for this day")
        else:
            s = _grade(w, WAVE_CAUTION_M, WAVE_BLOCKED_M)
            status = max(status, s, key=RANK.get)
            why.append(f"waves up to {w:.1f} m (forecast)")
        if g is not None:
            status = max(status, _grade(g, GUST_CAUTION_KMH, GUST_BLOCKED_KMH), key=RANK.get)
            why.append(f"gusts up to {g:.0f} km/h (forecast)")
        for t in tmd:
            if t.get("until") and t["until"] >= d:
                s = "blocked" if t.get("small_boats_ashore") else "caution"
                status = max(status, s, key=RANK.get)
                why.append(f"TMD Gulf wave bulletin {t['issue']}"
                           + (" (small boats ashore)" if t.get("small_boats_ashore") else ""))
                break
        if i < 3 and cyc["status"] in ("caution", "blocked"):
            status = max(status, cyc["status"], key=RANK.get)
            why.append(cyc["reason"])
        verdict = {"ok": "crossing conditions look normal",
                   "caution": "possible, but expect delays or cancellations",
                   "blocked": "ferries likely suspended",
                   "unknown": "cannot be assessed"}[status]
        out.append({"date": d, "label": fmt_day(d), "ok": status == "ok", "status": status,
                    "reason": f"{verdict.capitalize()}: {', '.join(why)}.",
                    "kind": "forecast", "valid_for": d,
                    "wave_max_m": None if w is None else round(w, 1),
                    "gust_max_kmh": None if g is None else round(g)})
    return out


def recommendation(lv: dict, signals: list[dict], wins: list[dict]) -> str:
    level, floor = lv.get("level"), lv.get("level_floor")
    sea_ids = ("waves", "tmd_sea", "gusts", "cyclone")
    worst = max((s["status"] for s in signals if s["id"] in sea_ids), key=RANK.get,
                default="unknown")
    rain = next((s for s in signals if s["id"] == "rain"), None)
    rain_txt = (" Heavy rain is possible (TMD bulletin or forecast): allow for flooded roads to the "
                "piers and on the mainland." if rain and RANK[rain["status"]] >= RANK["caution"] else "")
    sea_closed = any(s["status"] == "blocked" for s in signals
                     if s["id"] in ("waves", "tmd_sea", "cyclone"))
    good = [w["date"] for w in wins if w["ok"]]
    nxt = (f" Next days with normal crossing conditions (forecast): "
           f"{', '.join(fmt_day(g) for g in good[:3])}.") if good else \
        " No day in the next 7 shows normal crossing conditions (or the forecast is missing)."
    cyc = next((s for s in signals if s["id"] == "cyclone"), None)
    cyc_txt = ""
    if cyc and cyc["status"] in ("caution", "blocked"):
        cyc_txt = (" A tropical cyclone is within 800 km: if you intend to leave, go before the "
                   "sea rises; ferries stop around 2-3 m waves.")
    if level is None:
        return ("The risk level cannot be assessed (critical data missing"
                + (f"; at least '{risk.LEVEL_KEYS[floor]}'" if floor else "") + "). Check the "
                "TMD (1182) and the ferry operators directly before deciding." + cyc_txt + nxt)
    if level >= 4:
        if sea_closed:
            return ("LEAVE is advised but the sea route looks closed: check flights from Samui "
                    "(USM) now, otherwise shelter on high ground away from the shore and "
                    "follow the DDPM (1784)." + cyc_txt)
        return ("LEAVE the island while ferries and flights still run: go today if you can."
                + cyc_txt + nxt)
    if level == 3:
        return ("ACT: be ready to leave at short notice. Keep the go-bag by the door and a "
                "flexible ticket in mind; decide against your departure threshold." + rain_txt
                + cyc_txt + nxt)
    if level == 2:
        return ("PREPARE, no need to leave: build 14 days of self-sufficiency and know your "
                "exit route." + (" Crossing conditions are degraded right now." if
                                 RANK[worst] >= RANK["caution"] else "") + rain_txt
                + cyc_txt + nxt)
    return ("No reason to leave: adapt and keep a basic stock. The exit routes below are "
            "for reference." + cyc_txt)


def exit_plan() -> dict:
    today = today_bkk()
    s = db.get_status("local_risk")
    lv = s["value"] if s else risk.evaluate(save=True)
    cyc = cyclone_signal()
    signals = [sea_signal(today), tmd_sea_signal(), gust_signal(today), cyc, rain_signal(today)]
    wins = windows(today, cyc)
    return {
        "recommendation": recommendation(lv, signals, wins),
        "level": lv.get("level"), "level_key": lv.get("level_key"),
        "level_floor": lv.get("level_floor"), "evaluated_at": lv.get("evaluated_at"),
        "today": today.isoformat(),
        "signals": signals, "windows": wins, "routes": ROUTES, "checklist": CHECKLIST,
        "verified_at": VERIFIED_AT,
        "notes": [("Schedules and fares are not shown on purpose: they change. Check the "
                   "operator the same day."),
                  ("Wave heights are modelled for open water east of Samui; the Donsak car "
                   "ferries cross the more sheltered southwest side, the Chumphon catamaran "
                   "the open Gulf."),
                  "Unknown means the data is missing or stale, never that it is safe."],
    }


async def verify_route_urls() -> list[dict]:
    """Hits every route URL (manual check, never run by tests)."""
    import re

    import httpx

    urls = {r["url"] for r in ROUTES} | {u for r in ROUTES
                                         for u in re.findall(r"https://\S+?(?=[\s,)]|$)",
                                                             r["notes"])}
    out = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (elnino-watch route check)"}) as c:
        for u in sorted(urls):
            try:
                r = await c.get(u)
                out.append({"url": u, "status": r.status_code, "final": str(r.url)})
            except httpx.HTTPError as e:
                out.append({"url": u, "status": None, "error": type(e).__name__})
    return out


if __name__ == "__main__":  # python -m app.local.exit --verify
    import asyncio
    import json
    import sys

    if "--verify" in sys.argv:
        print(json.dumps(asyncio.run(verify_route_urls()), indent=1))
