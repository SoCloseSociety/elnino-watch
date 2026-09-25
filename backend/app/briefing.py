"""Situation briefing: a deterministic, rules-based English summary built from the DB.

Every sentence is assembled from stored values (with their dates and links); no
number is invented. Optionally (settings.computeforge_key) the text is sent to
ComputeForge (Anthropic Messages API shape) to be rewritten as smoother prose
WITHOUT adding facts. The LLM output is rejected, and the rules text kept, if
it contains a number that is not in the rules text, if the call fails, or if
the model refuses / is cut off; the reason is stored in `llm_error`.

Stored as status `briefing`; regenerated every 6 h and whenever the Koh Samui
level changes (scheduler -> refresh_if_due).
"""

from __future__ import annotations

import logging
import math
import re
from datetime import UTC, date, datetime, timedelta

import httpx

from . import db
from .collectors import source_report
from .collectors.base import parse_when
from .config import settings
from .local import provenance as P
from .local.provenance import fmt_day, fmt_ict, fmt_period, fmt_short, fmt_val

log = logging.getLogger("elnino.briefing")

EVERY = timedelta(hours=6)
NEAR_KM_DEFAULT = 800.0
LEVEL_NAMES = {0: "NORMAL", 1: "VIGILANCE", 2: "PREPARE", 3: "ACT", 4: "LEAVE"}
SEV_RANK = {"red": 0, "orange": 1, "green": 2, "info": 3}

SYSTEM_PROMPT = (
    "You edit a situation briefing about El Nino and a watched home on Koh Samui, "
    "Thailand. Rewrite the FACTS below into clear, calm, plain English for its residents. "
    "Strict rules: use only the facts given; do not add any fact, cause, forecast, "
    "advice, place or number that is not in the facts; copy every number, date and "
    "percentage exactly as written; keep every source status, data gap and stale-data "
    "warning; keep the section order and headings; no em dashes; no markdown tables. "
    "Output only the rewritten briefing text."
)


# ------------------------------------------------------------------ helpers


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _obs(series: str, now_s: str) -> dict | None:
    rows = db.query(
        "SELECT source, ts, value, unit, meta FROM observations WHERE series=? AND ts<=? "
        "ORDER BY ts DESC LIMIT 1", (series, now_s))
    return rows[0] if rows else None


def _status(key: str) -> dict | None:
    s = db.get_status(key)
    return s["value"] if s else None


def _day(ts: str | None) -> str:
    return (ts or "?")[:10]


def _dayl(ts: str | None, year: bool = True) -> str:
    """'2026-09-10' -> 'Thu 10 Sep 2026' (weekday computed)."""
    if not ts:
        return "?"
    try:
        return fmt_day(ts[:10], year)
    except ValueError:
        return ts


def _deg(v: float, d: int) -> str:
    return fmt_val(v, "degC", d, True)


def enso_strength(oni: float) -> str:
    """Conventional ONI categories (NOAA): +0.5 weak, +1.0 moderate, +1.5 strong,
    +2.0 very strong; mirrored for La Nina."""
    a = abs(oni)
    if a < 0.5:
        return "ENSO-neutral"
    phase = "El Nino" if oni > 0 else "La Nina"
    size = ("weak" if a < 1.0 else "moderate" if a < 1.5 else "strong" if a < 2.0
            else "very strong")
    return f"{size} {phase}"


def _season_txt(row: dict) -> str:
    season = (row.get("meta") or {}).get("season")
    if season:
        a, b = P.season_interval(row["ts"])
        return f"{season} ({fmt_period(a, b)})"
    return _day(row["ts"])


# ------------------------------------------------------------------ sections


def _enso(now_s: str) -> tuple[dict, str | None]:
    bullets, srcs, head = [], [], None
    cpc = _status("cpc_alert")
    if cpc:
        nxt = f"; next update {_dayl(cpc['next_issue'])}" if cpc.get("next_issue") else ""
        bullets.append(f"NOAA CPC status (bulletin): {cpc.get('status')} (issued "
                       f"{_dayl(cpc.get('issued'))}{nxt}).")
        srcs.append({"title": "NOAA CPC ENSO Diagnostic Discussion", "url": cpc.get("url")})
    oni = _obs("oni", now_s)
    roni = _obs("roni", now_s)
    wk = _obs("nino34_weekly_anom", now_s)
    if roni:
        bullets.append(f"RONI (NOAA's official index since 2026, observed): "
                       f"{_deg(roni['value'], 2)} for {_season_txt(roni)} = "
                       f"{enso_strength(roni['value'])} range.")
        srcs.append({"title": "NOAA CPC RONI",
                     "url": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"})
    if oni:
        cls = enso_strength(oni["value"])
        season = (oni.get("meta") or {}).get("season") or _day(oni["ts"])
        bits = [f"ONI {_deg(oni['value'], 2)}, {season}"]
        if roni:
            bits.append(f"RONI {_deg(roni['value'], 2)}")
        if wk:
            bits.append(f"Nino 3.4 {_deg(wk['value'], 1)} week of {fmt_short(wk['ts'])}")
        head = f"{cls[0].upper()}{cls[1:]} ({'; '.join(bits)})"
        bullets.append(f"ONI (3-month index, observed): {_deg(oni['value'], 2)} for "
                       f"{_season_txt(oni)} = {cls}.")
        srcs.append({"title": "NOAA CPC ONI", "url": "https://origin.cpc.ncep.noaa.gov/"
                     "products/analysis_monitoring/ensostuff/ONI_v5.php"})
    if wk:
        a, b = P.cpc_week(wk["ts"])
        bullets.append(f"Nino 3.4 weekly SST anomaly (NOAA CPC OISST, observed): "
                       f"{_deg(wk['value'], 1)} for the week {fmt_period(a, b)} {b[:4]} "
                       f"(centred on {_dayl(wk['ts'], False)}, UTC).")
    dy = _obs("nino34_daily_anom", now_s)
    if dy:
        prelim = ", preliminary" if (dy.get("meta") or {}).get("preliminary") else ""
        bullets.append(f"Nino 3.4 daily SST anomaly (OISST via Climate Reanalyzer{prelim}): "
                       f"{_deg(dy['value'], 2)} on {_dayl(dy['ts'])}.")
    soi = _obs("soi", now_s)
    bsoi = _obs("bom_soi", now_s)
    if soi or bsoi:
        parts = []
        if soi:
            parts.append(f"NOAA CPC standardized {soi['value']:+.1f} for "
                         f"{date.fromisoformat(soi['ts'][:10]):%b %Y}")
        if bsoi:
            parts.append(f"BoM (Troup) {bsoi['value']:+.1f} for "
                         f"{date.fromisoformat(bsoi['ts'][:10]):%b %Y}")
        bullets.append("Southern Oscillation Index (observed): " + "; ".join(parts)
                       + ". Sustained negative values (BoM below -7) = El Nino-like "
                       "atmosphere.")
    mei = _obs("mei_v2", now_s)
    if mei:
        season = (mei.get("meta") or {}).get("season") or _day(mei["ts"])
        bullets.append(f"MEI.v2 (NOAA PSL, observed): {mei['value']:+.2f} for {season}.")
    jma = _status("jma_outlook")
    if jma:
        bullets.append(f"JMA ({_dayl(jma.get('issued'))}): {jma.get('status')}")
        srcs.append({"title": "JMA El Nino Outlook", "url": jma.get("url")})
    if not bullets:
        bullets.append("No ENSO index or agency status stored yet: see "
                       "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/"
                       "enso_advisory/ensodisc.shtml")
    return {"id": "enso", "title": "ENSO state", "bullets": bullets, "sources": srcs}, head


def _forecast() -> dict:
    bullets, srcs = [], []
    iri = _status("iri_plume")
    if iri and iri.get("probabilities"):
        parts = [f"{p['season']} {p['el_nino']:.0f}%" for p in iri["probabilities"][:6]]
        bullets.append(f"IRI model-based forecast (issued {_dayl(iri.get('issued'))}), El Nino "
                       f"probability by 3-month season: {', '.join(parts)}.")
        last = iri["probabilities"][-1]
        bullets.append(f"Last season shown ({last['season']}): El Nino {last['el_nino']:.0f}%, "
                       f"neutral {last['neutral']:.0f}%, La Nina {last['la_nina']:.0f}%.")
        srcs.append({"title": "IRI ENSO forecast", "url": iri.get("url")})
    cpc = _status("cpc_alert")
    if cpc and cpc.get("synopsis"):
        bullets.append(f"NOAA CPC synopsis ({_dayl(cpc.get('issued'))}): {cpc['synopsis']}")
    if not bullets:
        bullets.append("No forecast probabilities stored yet: see "
                       "https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/")
    return {"id": "forecast", "title": "Forecast", "bullets": bullets, "sources": srcs}


def _factor_line(f: dict) -> str:
    """'Water: NORMAL -- 103% of normal (...) [ERA5 reanalysis, 2026-06-21/2026-09-18]'."""
    val = f.get("value_label")
    if not val and f.get("value") is not None:
        val = f"{f['value']} {f.get('unit_label') or P.unit_label(f.get('unit')) or ''}".strip()
    kind = f.get("kind")
    tag = []
    if kind:
        tag.append(P.KIND_LABELS.get(kind, kind))
    if f.get("valid_for"):
        tag.append(f"valid for {f['valid_for']}")
    elif f.get("observed_at"):
        tag.append(f"observed {f['observed_at']}")
    tags = f" [{', '.join(tag)}]" if tag else ""
    stale = " [stale data]" if f.get("stale") else ""
    return (f"{f['label']}: {(f.get('level_key') or '').upper()}"
            + (f" -- {val}" if val else "") + f"{tags}{stale}.")


def _local() -> tuple[dict, int | None, str, str | None]:
    risk = _status("local_risk")
    name = settings.home_name
    if not risk:
        return ({"id": "local", "title": name, "bullets": [
            f"The {name} risk engine has not produced an evaluation yet."], "sources": []},
            None, "unknown", None)
    lvl = risk.get("level")
    key = risk.get("level_key") or "unknown"
    label = LEVEL_NAMES.get(lvl, "UNKNOWN (insufficient data)") if lvl is not None else \
        "UNKNOWN (insufficient data)"
    bullets = [f"Level: {label} (evaluated {fmt_ict(risk.get('evaluated_at')) or '?'}). "
               f"{risk.get('headline', '')}".strip()]
    factors = [f for f in risk.get("factors") or [] if f.get("level") is not None]
    factors.sort(key=lambda f: -f["level"])
    srcs = []
    for f in factors:
        bullets.append(_factor_line(f))
        if f.get("url"):
            srcs.append({"title": f.get("source") or f["label"], "url": f["url"]})
    cov = risk.get("coverage") or {}
    missing = cov.get("missing") or risk.get("missing") or []
    if missing:
        crit = cov.get("critical_missing") or []
        bullets.append("Factors without data: " + ", ".join(missing)
                       + (f" (critical: {', '.join(crit)})" if crit else "")
                       + ". Their absence is not an all-clear: each factor card says what is "
                       "missing, why, and what to check by hand.")
    if cov.get("stale"):
        bullets.append("Factors with stale data: " + ", ".join(cov["stale"]) + ".")
    for a in (risk.get("actions") or [])[:3]:
        bullets.append(f"Action ({a.get('level_key')}): {a.get('text')}")
    return ({"id": "local", "title": name, "bullets": bullets, "sources": srcs[:5]}, lvl, key,
            risk.get("headline_local"))


def _hazards(now: datetime) -> dict:
    home = (settings.home_lat, settings.home_lon)
    radius = settings.home_radius_km or NEAR_KM_DEFAULT
    evs = db.query("SELECT source, category, title, url, severity, lat, lon, updated_at, "
                   "started_at FROM events WHERE lat IS NOT NULL AND lon IS NOT NULL")
    near, major = [], []
    for e in evs:
        d = _km(home[0], home[1], e["lat"], e["lon"])
        e["km"] = round(d)
        if d <= radius:
            near.append(e)
        elif e["source"] == "gdacs" and e["severity"] in ("orange", "red"):
            # "major" = an official GDACS alert level; FIRMS colours are detection counts
            major.append(e)

    def key(e):
        return (SEV_RANK.get(e["severity"] or "info", 9), e["km"])

    bullets, srcs = [], []
    near.sort(key=key)
    shown = [e for e in near if e["category"] != "wildfire" or e["severity"] in ("orange", "red")]
    fires = [e for e in near if e["category"] == "wildfire" and e not in shown]
    for e in shown[:6]:
        when = _day(e["updated_at"] or e["started_at"])
        bullets.append(f"Within {radius:,.0f} km: {e['category']} -- {e['title']} "
                       f"({e['severity'] or 'n/a'}, {e['km']:,} km away, updated {when} UTC).")
        if e.get("url"):
            srcs.append({"title": e["title"], "url": e["url"]})
    if fires:
        bullets.append(f"Within {radius:,.0f} km: {len(fires)} minor fire cluster(s) "
                       f"(green, NASA FIRMS satellite detections), nearest "
                       f"{min(f['km'] for f in fires):,} km.")
    if not shown and not fires:
        cyc = sorted((e for e in evs if e["category"] == "cyclone"), key=lambda e: e["km"])
        near_c = (f" Nearest tropical cyclone: {cyc[0]['title']} ({cyc[0]['severity']}), "
                  f"{cyc[0]['km']:,} km away." if cyc else "")
        bullets.append(f"No hazard event stored within {radius:,.0f} km of "
                       f"{settings.home_name}.{near_c}")
    major.sort(key=lambda e: (SEV_RANK.get(e["severity"], 9),
                              -(parse_when(e["updated_at"] or e["started_at"]) or now)
                              .timestamp()))
    if major:
        reds = sum(1 for e in major if e["severity"] == "red")
        bullets.append(f"Worldwide: {len(major)} GDACS orange/red alerts, {reds} red.")
        for e in major[:5]:
            bullets.append(f"{(e['severity'] or '').upper()} {e['category']}: {e['title']} "
                           f"({e['km']:,} km away, updated {_day(e['updated_at'] or e['started_at'])}"
                           " UTC).")
            if e.get("url"):
                srcs.append({"title": e["title"], "url": e["url"]})
    return {"id": "hazards", "title": "Hazards", "bullets": bullets, "sources": srcs[:8]}


def _official(now_s: str) -> dict:
    rows = db.query(
        "SELECT source, title, url, published_at FROM feed_items WHERE kind='official' "
        "AND published_at IS NOT NULL AND published_at<=? ORDER BY published_at DESC LIMIT 5",
        (now_s,))
    bullets = [f"{_day(r['published_at'])}: {r['title']}" for r in rows]
    if not bullets:
        bullets = ["No official bulletin stored yet."]
    return {"id": "official", "title": "Latest official bulletins", "bullets": bullets,
            "sources": [{"title": r["title"], "url": r["url"]} for r in rows if r["url"]]}


def _dur(sec: int) -> str:
    return f"{sec // 86400} d" if sec >= 86400 else f"{sec // 3600} h"


def _gaps(now: datetime) -> dict:
    rep = source_report(now)
    by: dict[str, list[str]] = {}
    for s in rep:
        if s["state"] in ("error", "stale", "needs_config", "pending"):
            by.setdefault(s["state"], []).append(s["name"])
    bullets = []
    stale = [s for s in rep if s["state"] == "stale"]
    for s in stale:
        f = s["freshness"]
        bullets.append(f"STALE: {s['title']} -- newest data {_day(f['newest_data_at'])} "
                       f"(allowed age {_dur(f['max_age_s'])}).")
    if by.get("error"):
        bullets.append("Failing on last run: " + ", ".join(by["error"]) + ".")
    if by.get("needs_config"):
        bullets.append("Not configured (optional credentials): " + ", ".join(by["needs_config"])
                       + ".")
    if by.get("pending"):
        bullets.append("Not run yet: " + ", ".join(by["pending"]) + ".")
    ok = sum(1 for s in rep if s["state"] == "ok")
    bullets.insert(0, f"{ok} of {len(rep)} sources fresh and OK.")
    return {"id": "gaps", "title": "Data gaps", "bullets": bullets, "sources": []}


def render_text(headline: str, sections: list[dict]) -> str:
    out = [headline, ""]
    for s in sections:
        out.append(f"{s['title']}:")
        out += [f"- {b}" for b in s["bullets"]]
        out.append("")
    return "\n".join(out).strip()


def build_rules(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    now_s = now.replace(microsecond=0).isoformat()
    enso, enso_head = _enso(now_s)
    local, lvl, key, local_txt = _local()
    sections = [enso, _forecast(), local, _hazards(now), _official(now_s), _gaps(now)]
    lvl_txt = LEVEL_NAMES.get(lvl) if lvl is not None else "UNKNOWN (insufficient data)"
    cpc = _status("cpc_alert")
    cpc_txt = (f"; NOAA CPC: {cpc['status']} ({fmt_short(cpc['issued'])})"
               if cpc and cpc.get("status") and cpc.get("issued") else "")
    headline = (f"{enso_head or 'ENSO state unknown (no ONI stored)'}{cpc_txt}. "
                f"{settings.home_name}: {lvl_txt}." + (f" {local_txt}" if local_txt else ""))
    return {"generated_at": now_s, "method": "rules", "model": None, "headline": headline,
            "sections": sections, "text": render_text(headline, sections),
            "local_level": lvl, "local_level_key": key}


# ------------------------------------------------------------------ LLM polish

# whole numeric tokens: 1.80, 2026-09-24, 13:40:45, 223/2569 (so a "40" cannot hide
# inside a timestamp of the facts)
_NUM_RE = re.compile(r"\d+(?:[.,:/-]\d+)*")


def unknown_numbers(rules_text: str, llm_text: str) -> list[str]:
    """Numbers in the LLM text that do not appear in the rules text (= invented)."""
    have = set(_NUM_RE.findall(rules_text))
    return sorted({n for n in _NUM_RE.findall(llm_text) if n not in have})


async def polish(doc: dict, client: httpx.AsyncClient | None = None) -> dict:
    """Rewrite doc['text'] via ComputeForge. Never raises: on any problem returns the
    rules doc with `llm_error` set."""
    if not settings.computeforge_key:
        return doc
    url = settings.computeforge_url.rstrip("/") + "/v1/messages"
    body = {
        "model": settings.briefing_model, "max_tokens": 4000, "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": "FACTS:\n\n" + doc["text"]}],
    }
    headers = {"x-api-key": settings.computeforge_key, "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    own = client is None
    c = client or httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    try:
        r = await c.post(url, json=body, headers=headers)
        if r.status_code != 200:
            return {**doc, "llm_error": f"http {r.status_code}: {r.text[:200]}"}
        data = r.json()
        stop = data.get("stop_reason")
        if stop not in ("end_turn", "stop_sequence"):
            return {**doc, "llm_error": f"stop_reason {stop}"}
        text = "".join(b.get("text", "") for b in data.get("content") or []
                       if b.get("type") == "text").strip()
        if not text:
            return {**doc, "llm_error": "empty text"}
        bad = unknown_numbers(doc["text"], text)
        if bad:
            return {**doc, "llm_error": f"rejected: numbers not in the facts: {bad[:10]}"}
        return {**doc, "method": "llm", "model": data.get("model") or settings.briefing_model,
                "text": text.replace("\u2014", "--"), "rules_text": doc["text"]}
    except Exception as e:  # noqa: BLE001 -- the rules briefing must always survive
        return {**doc, "llm_error": f"{type(e).__name__}: {e}"[:300]}
    finally:
        if own:
            await c.aclose()


# ------------------------------------------------------------------ lifecycle


def current() -> dict | None:
    return _status("briefing")


def is_due(now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    prev = current()
    if not prev:
        return True
    t = parse_when(prev.get("generated_at"))
    if t is None or now - t >= EVERY:
        return True
    risk = _status("local_risk")
    return bool(risk) and risk.get("level") != prev.get("local_level")


async def refresh(force: bool = False, client: httpx.AsyncClient | None = None) -> dict:
    if not force and not is_due():
        return current()  # type: ignore[return-value]
    doc = await polish(build_rules(), client)
    if doc.get("llm_error"):
        log.warning("briefing: LLM polish skipped: %s", doc["llm_error"])
    db.set_status("briefing", doc)
    return doc


async def refresh_if_due() -> dict | None:
    return await refresh() if is_due() else None
