"""SEO for the single-page app: what a crawler (or a browser without JS) gets.

Registered by app.main BEFORE the SPA catch-all, so these routes win:

- `GET /`, `/map`, `/indices`, `/news`, `/samui`, `/history`, `/prep`, `/places`, `/cams`,
  `/learn`, `/sources` and `/learn/<topic_id>`: frontend/dist/index.html with the <head> rewritten
  for that route (title, description, canonical, hreflang, Open Graph, Twitter card,
  JSON-LD) and, inside `<div id="root">`, a server-rendered text summary built from the
  DB (live ONI / RONI / Nino 3.4, NOAA status, IRI probabilities, Koh Samui level, each
  with its as-of date). React replaces that summary on mount (createRoot clears the
  container), crawlers index it as-is. Nothing here is invented: every number comes from
  the observations / status tables, and a missing value is shown as missing.
- `GET /sitemap.xml` (lastmod from real data updates), `GET /robots.txt`,
  `GET /og/current.png` (a 1200x630 Open Graph card drawn with Pillow from the live
  facts, cached 1 h), `GET /<indexnow key>.txt`.
- 301s for the legacy French paths and trailing-slash variants.

CSP: the injected <script> blocks (JSON-LD + the route map the frontend hook reads) are
hashed and added to script-src for that response, next to the hashes app/security.py
computes for the built index.html. JSON data blocks are never executed by browsers, but
script-src is still declared for them so nothing can ever show up as a violation.

Everything derives from `settings.public_origin` (env PUBLIC_ORIGIN): switching to
https://elnino.soclose.co is one setting. Learn content (243 topics, FAQ, myths) is read
from frontend/{dist,public}/seo/*.json, generated at build by frontend/scripts/prerender.mjs.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import re
import time
import unicodedata
from datetime import UTC, datetime
from html import escape
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from . import db, scheduler, security
from .config import ROOT, settings

log = logging.getLogger(__name__)
router = APIRouter()

DIST = ROOT / "frontend" / "dist"
SEO_DATA_DIRS = (DIST / "seo", ROOT / "frontend" / "public" / "seo")
FACTS_TTL_S = 60.0
OG_TTL_S = 3600.0
SITEMAP_TTL_S = 300.0
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
DISPOSABLE_HOST_SUFFIXES = (".sslip.io", ".nip.io", "localhost", "127.0.0.1")

# --------------------------------------------------------------------------- route metadata
# title <= 60 chars, description 140-160 chars (tests enforce it). English only.

ROUTES: dict[str, dict[str, str]] = {
    "/": {
        "name": "Overview",
        "title": "El Nino 2026-27 Live Tracker: ONI, Nino 3.4, Forecasts",
        "description": (
                        "Live El Nino 2026-27 tracker: NOAA ONI and RONI, weekly Nino 3.4 "
                        "anomaly, IRI and CPC forecasts, a hazards map and a Koh Samui (Thailand) "
                        "risk watch."),
    },
    "/map": {
        "name": "Live map",
        "title": "El Nino Live Map: Satellite Layers, Hazards, Buoys",
        "description": (
                        "Interactive El Nino map: NASA sea surface temperature anomaly, rainfall, "
                        "Himawari clouds, fires, GDACS disaster alerts and TAO buoys, Pacific to "
                        "Thailand."),
    },
    "/indices": {
        "name": "Indices",
        "title": "ENSO Indices Today: ONI, RONI, Nino 3.4, SOI, MEI",
        "description": (
                        "Every ENSO index with its latest value and history: NOAA ONI and RONI, "
                        "weekly Nino 1+2, 3, 3.4 and 4 anomalies, SOI (CPC and BoM), MEI.v2 and "
                        "global SST."),
    },
    "/news": {
        "name": "News and social",
        "title": "El Nino News, Official Bulletins and Social Posts",
        "description": (
                        "El Nino 2026 news, NOAA, BoM, WMO and TMD bulletins, research and social "
                        "posts in one feed, tagged for Thailand and Koh Samui and refreshed every "
                        "few minutes."),
    },
    "/samui": {
        "name": "Koh Samui watch",
        "title": "Koh Samui El Nino Risk Watch: Drought, Heat, Storms",
        "description": (
                        "Koh Samui (Thailand) El Nino risk level today: water supply, rain vs "
                        "normal, heat, flood, cyclone, sea state, air quality and coral heat "
                        "stress, with sources."),
    },
    "/history": {
        "name": "Past El Ninos",
        "title": "Past El Ninos on Koh Samui: 1982 to 2024 vs 2026-27",
        "description": (
                        "What the 7 strong El Ninos since 1982 did to Koh Samui: monsoon and "
                        "dry-season rain vs normal, heat, dry spells and documented water "
                        "shortages, next to 2026-27."),
    },
    "/prep": {
        "name": "Preparedness",
        "title": "El Nino Preparedness Guide for Koh Samui, Thailand",
        "description": (
                        "Preparedness checklist for a strong El Nino on Koh Samui: water storage, "
                        "food, power cuts, heat, haze, floods and an exit plan, with quantities "
                        "and local shops."),
    },
    "/places": {
        "name": "Places",
        "title": "Compare Places: El Nino Exposure and Local Risk",
        "description": (
                        "Compare El Nino exposure and current local risk between places (Koh "
                        "Samui, France, Russia and more): rain vs normal, heat, cyclones, fires, "
                        "ENSO teleconnection."),
    },
    "/cams": {
        "name": "Cams",
        "title": "Live Webcams: Koh Samui, Gulf of Thailand, Pacific",
        "description": (
                        "Public live webcams and satellite cams to see the weather yourself: Koh "
                        "Samui beaches, Gulf of Thailand ports, NOAA BuoyCAMs in the Pacific and "
                        "Himawari loops."),
    },
    "/learn": {
        "name": "Learn",
        "title": "Learn El Nino: 240+ Plain-English Explainers and FAQ",
        "description": (
                        "El Nino explained in plain English: what ENSO is, how to read ONI, RONI, "
                        "Nino 3.4, SOI and MEI, forecasts, the Koh Samui risk levels, myths vs "
                        "facts and a FAQ."),
    },
    "/sources": {
        "name": "Sources",
        "title": "Data Sources and Freshness: NOAA, IRI, BoM, TMD, NASA",
        "description": (
                        "Every data source behind the tracker with provider, update interval, "
                        "last fetch and freshness: NOAA CPC, IRI, BoM, TMD, NASA, GDACS, Open- "
                        "Meteo, Copernicus."),
    },
}
LEGACY_REDIRECTS = {"/carte": "/map", "/actualites": "/news", "/preparation": "/prep"}
TITLE_MAX, DESC_MIN, DESC_MAX = 60, 140, 160

# Series shown in the crawler summaries and described as Datasets (JSON-LD).
INDEX_SERIES: list[dict[str, Any]] = [
    {"source": "cpc_oni", "series": "oni", "label": "ONI (Oceanic Nino Index)", "unit": "°C",
     "period": "season", "topic": "oni"},
    {"source": "cpc_roni", "series": "roni", "label": "RONI (Relative Oceanic Nino Index)",
     "unit": "°C", "period": "season", "topic": "roni"},
    {"source": "cpc_weekly_sst", "series": "nino34_weekly_anom",
     "label": "Nino 3.4 weekly SST anomaly", "unit": "°C", "period": "week", "topic": "nino34"},
    {"source": "cpc_weekly_sst", "series": "nino34_weekly_sst", "label": "Nino 3.4 weekly SST",
     "unit": "°C", "period": "week", "topic": "nino34"},
    {"source": "cpc_soi", "series": "soi", "label": "SOI (Southern Oscillation Index, CPC)",
     "unit": "std", "period": "month", "topic": "soi"},
    {"source": "bom_soi", "series": "bom_soi", "label": "SOI (BoM, Troup)", "unit": "index",
     "period": "month", "topic": "bom_soi"},
    {"source": "psl_mei", "series": "mei_v2", "label": "MEI.v2 (Multivariate ENSO Index)",
     "unit": "index", "period": "bimonth", "topic": "mei_v2"},
    {"source": "cr_world_sst", "series": "world_sst_daily", "label": "World sea surface temperature",
     "unit": "°C", "period": "day", "topic": "world_sst"},
]

DATASETS: list[dict[str, Any]] = [
    {
        "id": "oni-roni",
        "name": "Oceanic Nino Index (ONI) and Relative ONI (RONI), monthly since 1950",
        "description": ("3-month running mean of the Nino 3.4 sea surface temperature anomaly "
                        "(ERSSTv6) published by NOAA CPC; RONI is the same index relative to "
                        "the tropical mean SST. El Nino threshold +0.5 °C."),
        "series": [("cpc_oni", "oni", "ONI"), ("cpc_roni", "roni", "RONI")],
        "box": "-5 -170 5 -120",
        "provider": "NOAA Climate Prediction Center",
        "isBasedOn": ["https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/",
                      "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"],
        "license": "https://www.noaa.gov/information-technology/open-data-dissemination",
        "license_note": "NOAA data: US Government work, public domain; cite NOAA CPC.",
        "keywords": ["ONI", "RONI", "El Nino", "ENSO", "Nino 3.4", "NOAA CPC"],
    },
    {
        "id": "nino34-weekly",
        "name": "Nino 3.4 weekly sea surface temperature and anomaly (OISST v2.1), since 1981",
        "description": ("Weekly Nino 3.4 (5N-5S, 170W-120W) SST and anomaly from NOAA CPC's "
                        "weekly ENSO update (OISST v2.1, 1991-2020 climatology)."),
        "series": [("cpc_weekly_sst", "nino34_weekly_sst", "Nino 3.4 SST"),
                   ("cpc_weekly_sst", "nino34_weekly_anom", "Nino 3.4 SST anomaly")],
        "box": "-5 -170 5 -120",
        "provider": "NOAA Climate Prediction Center",
        "isBasedOn": ["https://www.cpc.ncep.noaa.gov/data/indices/"],
        "license": "https://www.noaa.gov/information-technology/open-data-dissemination",
        "license_note": "NOAA data: US Government work, public domain; cite NOAA CPC.",
        "keywords": ["Nino 3.4", "weekly SST anomaly", "El Nino", "OISST"],
    },
    {
        "id": "soi",
        "name": "Southern Oscillation Index (SOI), NOAA CPC and Australian BoM, monthly",
        "description": ("Standardised Tahiti minus Darwin sea-level pressure difference: CPC "
                        "series since 1951 and the BoM (Troup) series since 1876. Sustained "
                        "negative values accompany El Nino."),
        "series": [("cpc_soi", "soi", "SOI (CPC)"), ("bom_soi", "bom_soi", "SOI (BoM)")],
        "box": "-18 130 -12 -149",
        "provider": "NOAA CPC and Australian Bureau of Meteorology",
        "isBasedOn": ["https://www.cpc.ncep.noaa.gov/data/indices/soi",
                      "http://www.bom.gov.au/climate/enso/soi/"],
        "license": "http://www.bom.gov.au/other/copyright.shtml",
        "license_note": ("CPC part: NOAA public domain. BoM part: Commonwealth of Australia "
                         "copyright notice, attribution required (see the BoM copyright page)."),
        "keywords": ["SOI", "Southern Oscillation Index", "Tahiti", "Darwin", "ENSO"],
    },
    {
        "id": "mei",
        "name": "Multivariate ENSO Index version 2 (MEI.v2), bi-monthly since 1979",
        "description": ("NOAA PSL's combined index of five ocean-atmosphere variables over the "
                        "tropical Pacific (30S-30N, 100E-70W), one value per overlapping "
                        "two-month season."),
        "series": [("psl_mei", "mei_v2", "MEI.v2")],
        "box": "-30 100 30 -70",
        "provider": "NOAA Physical Sciences Laboratory",
        "isBasedOn": ["https://psl.noaa.gov/enso/mei/"],
        "license": "https://www.noaa.gov/information-technology/open-data-dissemination",
        "license_note": "NOAA data: US Government work, public domain; cite NOAA PSL.",
        "keywords": ["MEI", "Multivariate ENSO Index", "El Nino", "NOAA PSL"],
    },
    {
        "id": "samui-weather",
        "name": "Koh Samui local weather, sea state and air quality (Open-Meteo), daily",
        "description": ("Daily maximum / minimum / feels-like temperature, rain, wind gusts, "
                        f"UV, wave height, sea surface temperature and PM2.5 for {settings.home_name} "
                        f"({settings.home_lat:.2f} N {settings.home_lon:.2f} E): model analysis for past days, forecast ahead."),
        "series": [("openmeteo_samui", "samui_temp_max", "Daily max temperature"),
                   ("openmeteo_samui", "samui_precip", "Daily rain"),
                   ("openmeteo_samui", "samui_wind_gust_max", "Daily max wind gust"),
                   ("openmeteo_marine", "samui_wave_height", "Significant wave height"),
                   ("openmeteo_samui_air", "samui_pm2_5", "PM2.5")],
        "point": True,
        "provider": "Open-Meteo",
        "isBasedOn": ["https://open-meteo.com/en/docs", "https://open-meteo.com/en/docs/marine-weather-api",
                      "https://open-meteo.com/en/docs/air-quality-api"],
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "license_note": "Open-Meteo: CC BY 4.0 (https://open-meteo.com/en/terms); attribution required.",
        "keywords": ["Koh Samui weather", "El Nino Thailand", "Gulf of Thailand", "PM2.5", "waves"],
    },
    {
        "id": "samui-era5-history",
        "name": "Koh Samui monthly rain and heat since 1950 (ERA5 reanalysis, home grid cell)",
        "description": ("Monthly rain total, maximum air temperature and maximum feels-like "
                        f"temperature for the ~30 km ERA5 grid cell holding {settings.home_name} "
                        "(9.5 N 100.0 E), 1950 to today, behind the El Nino analogs page "
                        "(1982-83 to 2023-24 vs 2026-27)."),
        "series": [("samui_era5_history", "samui_era5_month_precip", "Monthly rain (ERA5)"),
                   ("samui_era5_history", "samui_era5_month_temp_max", "Monthly max temperature (ERA5)"),
                   ("samui_era5_history", "samui_era5_month_apparent_max",
                    "Monthly max feels-like temperature (ERA5)")],
        "point": True, "page": "/history",
        "provider": "Open-Meteo (ECMWF ERA5)",
        "isBasedOn": ["https://open-meteo.com/en/docs/historical-weather-api",
                      "https://doi.org/10.1002/qj.3803"],
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "license_note": "Open-Meteo: CC BY 4.0 (https://open-meteo.com/en/terms); ERA5: Copernicus C3S licence; attribution required.",
        "keywords": ["Koh Samui rainfall history", "ERA5", "El Nino analogs", "1997-98", "2015-16",
                     "2023-24", "Thailand drought"],
    },
]


# --------------------------------------------------------------------------- small helpers


def origin() -> str:
    return settings.public_origin.rstrip("/")


def absolute(path: str) -> str:
    return origin() + path


def _fit(text: str, limit: int) -> str:
    """Cut at a word boundary with an ellipsis so the result is <= limit chars."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 3].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "..."


def _iso_date(ts: str | None) -> str | None:
    return ts[:10] if ts else None


def _fmt_day(ts: str | None) -> str:
    """'2026-09-16' or ISO datetime -> '16 Sep 2026'."""
    if not ts:
        return "n/a"
    try:
        d = datetime.fromisoformat(ts)
    except ValueError:
        return ts
    return f"{d.day} {d.strftime('%b %Y')}"


def _fmt_dt(ts: str | None) -> str:
    if not ts:
        return "n/a"
    try:
        d = datetime.fromisoformat(ts).astimezone(UTC)
    except ValueError:
        return ts
    return f"{d.day} {d.strftime('%b %Y %H:%M')} UTC"


_MONTHS = "JFMAMJJASOND"


def _season_code(ts: str) -> str:
    """Center month of a 3-month season -> 'JJA 2026' (CPC labelling, year of the centre)."""
    d = datetime.fromisoformat(ts[:10])
    m = d.month
    return f"{_MONTHS[(m - 2) % 12]}{_MONTHS[m - 1]}{_MONTHS[m % 12]} {d.year}"


def _signed(v: float | None, unit: str = "°C", decimals: int = 2) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.{decimals}f} {unit}".rstrip()


def _period_label(period: str, ts: str) -> str:
    if period == "season":
        return _season_code(ts)
    if period == "week":
        return f"week of {_fmt_day(ts)}"
    if period == "bimonth":
        d = datetime.fromisoformat(ts[:10])
        return f"{_MONTHS[d.month - 1]}{_MONTHS[d.month % 12]} {d.year}"
    if period == "month":
        return datetime.fromisoformat(ts[:10]).strftime("%b %Y")
    return _fmt_day(ts)


# --------------------------------------------------------------------------- Learn content

_learn_cache: tuple[float, dict] | None = None


def _read_json(name: str) -> dict | None:
    for d in SEO_DATA_DIRS:
        p = d / name
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                log.warning("seo: %s is not valid JSON", p)
    return None


def learn_content() -> dict:
    """{topics: {id: topic}, faq: [...], myths: [...], categories: [...], generated_at}.
    Cached on the mtime of topics.json; empty structures when the export is missing."""
    global _learn_cache
    mtime = 0.0
    for d in SEO_DATA_DIRS:
        p = d / "topics.json"
        if p.is_file():
            mtime = p.stat().st_mtime
            break
    if _learn_cache and _learn_cache[0] == mtime:
        return _learn_cache[1]
    topics = _read_json("topics.json") or {}
    faq = _read_json("faq.json") or {}
    myths = _read_json("myths.json") or {}
    out = {
        "topics": {t["id"]: t for t in topics.get("topics", [])},
        "categories": topics.get("categories", []),
        "faq": faq.get("items", []),
        "myths": myths.get("items", []),
        "generated_at": topics.get("generated_at"),
    }
    _learn_cache = (mtime, out)
    return out


# --------------------------------------------------------------------------- live facts

_facts_cache: tuple[float, dict] | None = None


def _latest(source: str, series: str) -> dict | None:
    rows = db.query(
        "SELECT ts, value, unit FROM observations WHERE source=? AND series=? AND ts <= ? "
        "ORDER BY ts DESC LIMIT 2", (source, series, db.now_iso()))
    if not rows:
        return None
    return {"ts": rows[0]["ts"], "value": rows[0]["value"], "unit": rows[0]["unit"],
            "prev": rows[1]["value"] if len(rows) > 1 else None,
            "prev_ts": rows[1]["ts"] if len(rows) > 1 else None}


def _status(key: str) -> dict | None:
    s = db.get_status(key)
    if not s or not isinstance(s.get("value"), dict):
        return None
    return s["value"] | {"_updated_at": s["updated_at"]}


def facts(force: bool = False) -> dict:
    """The live numbers every summary / JSON-LD / OG card is built from (60 s cache)."""
    global _facts_cache
    if not force and _facts_cache and time.monotonic() - _facts_cache[0] < FACTS_TTL_S:
        return _facts_cache[1]
    series = {f"{s['source']}/{s['series']}": _latest(s["source"], s["series"])
              for s in INDEX_SERIES}
    run = db.query("SELECT MAX(finished_at) AS t FROM source_runs WHERE ok=1")
    st = db.query("SELECT MAX(updated_at) AS t FROM status")
    out = {
        "oni": series["cpc_oni/oni"],
        "roni": series["cpc_roni/roni"],
        "nino34": series["cpc_weekly_sst/nino34_weekly_anom"],
        "nino34_sst": series["cpc_weekly_sst/nino34_weekly_sst"],
        "soi": series["cpc_soi/soi"],
        "bom_soi": series["bom_soi/bom_soi"],
        "mei": series["psl_mei/mei_v2"],
        "world_sst": series["cr_world_sst/world_sst_daily"],
        "series": series,
        "cpc": _status("cpc_alert"),
        "iri": _status("iri_plume"),
        "bom": _status("bom_outlook"),
        "local": _status("local_risk"),
        "briefing": _status("briefing"),
        "updated_at": (run[0]["t"] if run else None) or (st[0]["t"] if st else None),
    }
    _facts_cache = (time.monotonic(), out)
    return out


def invalidate_caches() -> None:
    global _facts_cache, _og_cache, _sitemap_cache
    _facts_cache = None
    _og_cache = None
    _sitemap_cache = None


def enso_phrase(f: dict) -> str | None:
    """'ONI +1.80 °C (JJA 2026), RONI +1.36 °C, Nino 3.4 +3.0 °C (week of 16 Sep 2026)'."""
    parts = []
    if f["oni"]:
        parts.append(f"ONI {_signed(f['oni']['value'])} ({_season_code(f['oni']['ts'])})")
    if f["roni"]:
        parts.append(f"RONI {_signed(f['roni']['value'])}")
    if f["nino34"]:
        parts.append(f"Nino 3.4 {_signed(f['nino34']['value'], decimals=1)} "
                     f"(week of {_fmt_day(f['nino34']['ts'])})")
    return ", ".join(parts) or None


# --------------------------------------------------------------------------- HTML summary

_MAIN_NAV = [("/", "Overview"), ("/map", "Live map"), ("/indices", "Indices"), ("/news", "News"),
             ("/samui", "Koh Samui watch"), ("/history", "Past El Ninos"), ("/cams", "Webcams"),
             ("/places", "Places"), ("/prep", "Preparedness"), ("/learn", "Learn"),
             ("/sources", "Sources")]


def _e(v: Any) -> str:
    return escape("" if v is None else str(v), quote=True)


def _a(href: str, text: str, external: bool = False) -> str:
    rel = ' rel="noopener"' if external else ""
    return f'<a href="{_e(href)}"{rel}>{_e(text)}</a>'


def _paras(text: str | None) -> str:
    """Plain text (blank line = paragraph, '- ' = bullet) -> <p> / <ul>."""
    if not text:
        return ""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if lines and all(re.match(r"^\s*- ", ln) for ln in lines):
            items = "".join(f"<li>{_e(re.sub(r'^\s*- ', '', ln))}</li>" for ln in lines)
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{_e(' '.join(ln.strip() for ln in lines))}</p>")
    return "".join(out)


def _dl(rows: list[tuple[str, str]]) -> str:
    return "<dl>" + "".join(f"<dt>{_e(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>"


def _facts_rows(f: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if f["oni"]:
        o = f["oni"]
        rows.append(("ONI (NOAA CPC)", _e(f"{_signed(o['value'])}, {_season_code(o['ts'])} "
                                          f"(previous {_signed(o['prev'])})")))
    else:
        rows.append(("ONI (NOAA CPC)", "no data yet"))
    if f["roni"]:
        r = f["roni"]
        rows.append(("RONI (NOAA CPC)", _e(f"{_signed(r['value'])}, {_season_code(r['ts'])}")))
    if f["nino34"]:
        n = f["nino34"]
        sst = f["nino34_sst"]
        txt = f"{_signed(n['value'], decimals=1)} anomaly, week of {_fmt_day(n['ts'])}"
        if sst and sst["ts"] == n["ts"] and sst["value"] is not None:
            txt += f" (SST {sst['value']:.1f} °C)"
        rows.append(("Nino 3.4 weekly (NOAA CPC / OISST)", _e(txt)))
    else:
        rows.append(("Nino 3.4 weekly", "no data yet"))
    if f["cpc"]:
        c = f["cpc"]
        rows.append(("NOAA CPC ENSO status", _e(f"{c.get('status')} (issued {_fmt_day(c.get('issued'))})")
                     + (f", {_e(c['synopsis'])}" if c.get("synopsis") else "")
                     + (f" {_a(c['url'], 'source', True)}" if c.get("url") else "")))
    if f["iri"] and f["iri"].get("probabilities"):
        probs = f["iri"]["probabilities"][:4]
        txt = "; ".join(f"{p['season']}: El Nino {p['el_nino']:.0f}%, neutral {p['neutral']:.0f}%, "
                        f"La Nina {p['la_nina']:.0f}%" for p in probs)
        rows.append((f"IRI ENSO probabilities (issued {_fmt_day(f['iri'].get('issued'))})", _e(txt)))
    if f["bom"] and f["bom"].get("status"):
        rows.append(("Australian BoM ENSO outlook",
                     _e(f"{f['bom']['status']} (issued {_fmt_day(f['bom'].get('issued'))})")))
    if f["local"]:
        lv = f["local"]
        rows.append(("Koh Samui watch level", _e(f"{lv.get('level_label') or lv.get('level_key')}"
                                                 f" (evaluated {_fmt_dt(lv.get('evaluated_at'))})")))
    rows.append(("Data updated", _e(_fmt_dt(f["updated_at"]))))
    return rows


def _nav_html(current: str) -> str:
    items = "".join(
        f'<li><a href="{p}"{" aria-current=page" if p == current else ""}>{_e(n)}</a></li>'
        for p, n in _MAIN_NAV)
    return f'<nav aria-label="Sections"><ul>{items}</ul></nav>'


def _summary_shell(path: str, h1: str, intro: str, body: str, f: dict) -> str:
    return (
        '<div id="prerender">'
        f"<header><p class=\"brand\">{_e(settings.site_name)}</p><h1>{_e(h1)}</h1>"
        f"<p>{_e(intro)}</p></header>"
        f"{body}"
        f"{_nav_html(path)}"
        f"<footer><p>Data as of {_e(_fmt_dt(f['updated_at']))}. Every value shown here was "
        "fetched from its source (NOAA CPC, IRI, BoM, TMD, NASA, Open-Meteo, GDACS and "
        "others) and carries its own date; nothing is estimated by this site. "
        f"Published by {_a(settings.org_url, settings.org_name, True)}.</p>"
        "<noscript><p>Charts, the live map and the interactive tools need JavaScript; the "
        "figures above are the same live data, rendered by the server.</p></noscript>"
        "</footer></div>"
    )


def _summary_overview(f: dict) -> str:
    body = "<section><h2>ENSO status now</h2>" + _dl(_facts_rows(f)) + "</section>"
    b = f["briefing"]
    if b and b.get("sections"):
        body += (f"<section><h2>Briefing ({_fmt_dt(b.get('generated_at'))})</h2>"
                 f"<p>{_e(b.get('headline'))}</p>")
        for s in b["sections"]:
            items = "".join(f"<li>{_e(x)}</li>" for x in s.get("bullets", []))
            body += f"<h3>{_e(s.get('title'))}</h3><ul>{items}</ul>"
        body += "</section>"
    lv = f["local"]
    if lv and lv.get("headline"):
        body += (f"<section><h2>Koh Samui, Thailand</h2><p>{_e(lv['headline'])}</p>"
                 f"<p>{_a('/samui', 'Full Koh Samui risk watch')}</p></section>")
    return body


def _summary_indices(f: dict) -> str:
    rows = []
    for s in INDEX_SERIES:
        v = f["series"].get(f"{s['source']}/{s['series']}")
        if not v or v["value"] is None:
            rows.append(f"<tr><td>{_e(s['label'])}</td><td colspan=3>no data yet</td></tr>")
            continue
        unit = s["unit"]
        val = f"{v['value']:+.2f} {unit}" if unit == "°C" else f"{v['value']:+.2f}"
        prev = "n/a" if v["prev"] is None else f"{v['prev']:+.2f}"
        rows.append(f"<tr><td>{_a('/learn/' + s['topic'], s['label'])}</td><td>{_e(val)}</td>"
                    f"<td>{_e(_period_label(s['period'], v['ts']))}</td><td>{_e(prev)}</td></tr>")
    table = ("<table><thead><tr><th>Index</th><th>Latest</th><th>Period</th><th>Previous</th>"
             "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
    return ("<section><h2>Latest values</h2>" + table + "</section><section><h2>Status</h2>"
            + _dl(_facts_rows(f)) + "</section>")


def _summary_samui(f: dict) -> str:
    lv = f["local"]
    if not lv:
        return ("<section><h2>Koh Samui risk level</h2><p>The risk engine has not produced an "
                "evaluation yet (no data). It never assumes safety.</p></section>")
    body = (f"<section><h2>Level: {_e(lv.get('level_label') or lv.get('level_key'))}</h2>"
            f"<p>{_e(lv.get('headline'))}</p>"
            f"<p>Evaluated {_e(_fmt_dt(lv.get('evaluated_at')))} for "
            f"{_e((lv.get('home') or {}).get('name') or settings.home_name)}.</p></section>")
    rows = []
    for fa in lv.get("factors", []):
        val = fa.get("value_label") or (f"{fa.get('value')} {fa.get('unit_label') or ''}".strip()
                                        if fa.get("value") is not None else "no data")
        rows.append(f"<tr><td>{_e(fa.get('label'))}</td><td>{_e(fa.get('level_key'))}</td>"
                    f"<td>{_e(val)}</td><td>{_e(fa.get('threshold'))}</td>"
                    f"<td>{_e(_fmt_dt(fa.get('as_of')))}</td>"
                    f"<td>{_a(fa['url'], fa.get('source') or 'source', True) if fa.get('url') else _e(fa.get('source'))}</td></tr>")
    if rows:
        body += ("<section><h2>Factors</h2><table><thead><tr><th>Factor</th><th>Level</th>"
                 "<th>Value</th><th>Threshold</th><th>As of</th><th>Source</th></tr></thead>"
                 "<tbody>" + "".join(rows) + "</tbody></table></section>")
    for key, title in (("actions", "What to do now"), ("triggers", "What would raise the level")):
        items = [x.get("text") for x in lv.get(key, []) if x.get("text")]
        if items:
            body += (f"<section><h2>{title}</h2><ul>"
                     + "".join(f"<li>{_e(t)}</li>" for t in items) + "</ul></section>")
    body += "<section><h2>ENSO context</h2>" + _dl(_facts_rows(f)[:4]) + "</section>"
    return body


def _summary_news(f: dict) -> str:
    rows = db.query(
        "SELECT source, kind, title, url, published_at, fetched_at FROM feed_items "
        "WHERE kind IN ('official','news','research') AND title IS NOT NULL "
        "ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT 20")
    if not rows:
        return "<section><h2>Latest items</h2><p>No items fetched yet.</p></section>"
    items = "".join(
        f"<li>{_a(r['url'], r['title'], True) if r.get('url') else _e(r['title'])}"
        f" <small>({_e(r['kind'])}, {_e(r['source'])}, "
        f"{_e(_fmt_day(r.get('published_at') or r.get('fetched_at')))})</small></li>" for r in rows)
    return f"<section><h2>Latest official bulletins, news and research</h2><ul>{items}</ul></section>"


def _summary_map(f: dict) -> str:
    cats = db.query("SELECT category, COUNT(*) AS n FROM events WHERE lat IS NOT NULL "
                    "GROUP BY category ORDER BY n DESC")
    body = "<section><h2>Events on the map now</h2>"
    if cats:
        body += "<ul>" + "".join(f"<li>{_e(c['category'])}: {c['n']}</li>" for c in cats) + "</ul>"
    else:
        body += "<p>No events fetched yet.</p>"
    body += "</section>"
    sev = db.query("SELECT title, category, source, severity, url, COALESCE(updated_at, started_at) AS t "
                   "FROM events WHERE severity IN ('red','orange') AND lat IS NOT NULL "
                   "ORDER BY t DESC LIMIT 15")
    if sev:
        items = "".join(
            f"<li>{_a(r['url'], r['title'], True) if r.get('url') else _e(r['title'])} "
            f"<small>({_e(r['severity'])} {_e(r['category'])}, {_e(r['source'])}, "
            f"{_e(_fmt_day(r['t']))})</small></li>" for r in sev)
        body += f"<section><h2>Red and orange alerts</h2><ul>{items}</ul></section>"
    body += "<section><h2>ENSO status</h2>" + _dl(_facts_rows(f)[:3]) + "</section>"
    return body


def _summary_prep(f: dict) -> str:
    try:
        from .local import preparedness as prep
    except ImportError:
        return ""
    body = "<section><h2>Checklist categories</h2>"
    for c in getattr(prep, "CATEGORIES", []):
        n = len(c.get("items", []))
        body += f"<h3>{_e(c.get('title'))}</h3><p>{_e(c.get('why'))} ({n} items)</p>"
    body += "</section>"
    contacts = getattr(prep, "CONTACTS", [])
    if contacts:
        body += "<section><h2>Emergency numbers (Thailand)</h2><ul>" + "".join(
            f"<li>{_e(c.get('label'))}: {_e(c.get('number') or c.get('url') or '')}</li>"
            for c in contacts) + "</ul></section>"
    lv = f["local"]
    if lv and lv.get("headline"):
        body += f"<section><h2>Why now</h2><p>{_e(lv['headline'])}</p></section>"
    return body


def _summary_places(f: dict) -> str:
    rows = db.query("SELECT value FROM status WHERE key LIKE 'place:%' OR key = 'places'")
    names: list[str] = []
    for r in rows:
        v = r.get("value")
        if isinstance(v, dict) and v.get("name"):
            names.append(v["name"])
        elif isinstance(v, list):
            names += [p.get("name") for p in v if isinstance(p, dict) and p.get("name")]
    body = ("<section><h2>How it works</h2><p>Each place gets the same factor engine as the "
            "Koh Samui watch (rain vs its own 1991-2020 normal, heat, flood, cyclones within "
            "800 km, fires, sea state, air quality) plus the ENSO teleconnection for its "
            "region, so two locations can be compared on the same scale.</p></section>")
    if names:
        body += ("<section><h2>Places currently compared</h2><ul>"
                 + "".join(f"<li>{_e(n)}</li>" for n in sorted(set(names))) + "</ul></section>")
    return body


def _summary_cams(f: dict) -> str:
    try:
        from . import cams_api
        cams, updated, _parts = cams_api._load()
    except (ImportError, AttributeError, TypeError, ValueError):  # the cams module is optional
        cams, updated = [], None
    if not cams:
        return ("<section><h2>Webcams</h2><p>Only feeds their owners publish for public "
                "viewing (tourism and beach cams, official weather, traffic and port cams, NOAA "
                "BuoyCAMs, Windy webcams). None listed yet.</p></section>")
    items = "".join(
        f"<li>{_e(c.get('title') or c.get('name'))}"
        f"{' (' + _e(c.get('area')) + ')' if c.get('area') else ''}</li>" for c in cams[:40])
    return (f"<section><h2>{len(cams)} public webcams (list updated {_e(_fmt_dt(updated))})</h2>"
            f"<ul>{items}</ul></section>")


def _summary_sources(f: dict) -> str:
    try:
        from .collectors import source_report
        rows = source_report()
    except (ImportError, AttributeError, TypeError, ValueError, KeyError):
        log.exception("seo: source_report failed")
        rows = []
    if not rows:
        return "<section><h2>Sources</h2><p>No collector report available.</p></section>"
    trs = "".join(
        f"<tr><td>{_a(r['homepage'], r['title'], True) if r.get('homepage') else _e(r['title'])}</td>"
        f"<td>{_e(r.get('provider'))}</td><td>{_e(r.get('category'))}</td>"
        f"<td>every {int((r.get('interval_s') or 0) / 60)} min</td><td>{_e(r.get('state'))}</td>"
        f"<td>{_e(_fmt_dt(r.get('last_ok_at')))}</td></tr>" for r in rows)
    return (f"<section><h2>{len(rows)} data sources</h2><table><thead><tr><th>Source</th>"
            "<th>Provider</th><th>Category</th><th>Interval</th><th>State</th><th>Last ok</th>"
            f"</tr></thead><tbody>{trs}</tbody></table></section>")


def _summary_learn(f: dict) -> str:
    lc = learn_content()
    topics = list(lc["topics"].values())
    body = ""
    if topics:
        body += f"<section><h2>Glossary: {len(topics)} explainers</h2>"
        for cat in lc["categories"]:
            ts = [t for t in topics if t["category"] == cat["id"]]
            if not ts:
                continue
            body += (f"<h3>{_e(cat['label'])}</h3><ul>" + "".join(
                f"<li>{_a('/learn/' + t['id'], t['title'])}: {_e(t['short'])}</li>"
                for t in ts) + "</ul>")
        body += "</section>"
    if lc["faq"]:
        body += "<section><h2>Frequently asked questions</h2>"
        for q in lc["faq"]:
            body += f"<h3 id=\"faq-{_e(q['id'])}\">{_e(q['question'])}</h3>{_paras(q['answer_text'])}"
        body += "</section>"
    if lc["myths"]:
        body += "<section><h2>Myths vs facts</h2><dl>" + "".join(
            f"<dt>Myth: {_e(m['myth'])}</dt><dd>Fact: {_e(m['fact'])}</dd>"
            for m in lc["myths"]) + "</dl></section>"
    body += "<section><h2>ENSO status now</h2>" + _dl(_facts_rows(f)[:3]) + "</section>"
    return body


def _summary_topic(t: dict, f: dict) -> str:
    body = f"<section><p><em>{_e(t['category_label'])}</em></p>{_paras(t['body'])}</section>"
    if t.get("how_to_read"):
        body += f"<section><h2>How to read it</h2>{_paras(t['how_to_read'])}</section>"
    if t.get("why_it_matters"):
        body += f"<section><h2>Why it matters for Koh Samui</h2>{_paras(t['why_it_matters'])}</section>"
    th = t.get("thresholds")
    if th and th.get("columns"):
        head = "".join(f"<th>{_e(c)}</th>" for c in th["columns"])
        rows = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>"
                       for r in th.get("rows", []))
        body += (f"<section><h2>Thresholds</h2><table><thead><tr>{head}</tr></thead>"
                 f"<tbody>{rows}</tbody></table>"
                 + (f"<p>{_e(th['note'])}</p>" if th.get("note") else "") + "</section>")
    if t.get("example"):
        body += f"<section><h2>Example</h2>{_paras(t['example'])}</section>"
    if t.get("sources"):
        body += "<section><h2>Sources</h2><ul>" + "".join(
            f"<li>{_a(s['url'], s['title'], True)}</li>" for s in t["sources"]) + "</ul></section>"
    if t.get("related"):
        body += "<section><h2>Related</h2><ul>" + "".join(
            f"<li>{_a('/learn/' + r['id'], r['title'])}</li>" for r in t["related"]) + "</ul></section>"
    body += "<section><h2>ENSO status now</h2>" + _dl(_facts_rows(f)[:3]) + "</section>"
    return body


def _n(v: Any, unit: str = "", decimals: int = 0) -> str:
    """A number with its unit, or 'n/a' (never an estimate) when the payload has none."""
    if v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        return f"{v:.{decimals}f}{unit}"
    return _e(v)


def _summary_history(f: dict) -> str:
    """The analogs page for crawlers: takeaways, the events table, impacts, method. Every
    number comes from GET /api/local/analogs (app.local.analogs.build); a value the
    reconstruction does not have yet is written 'n/a'."""
    try:
        from .local import analogs
        d = analogs.build()
    except Exception:  # the SEO page must never break on the analogs module
        log.exception("seo: analogs.build failed")
        return ("<section><h2>Past El Ninos</h2><p>The analog reconstruction is not available "
                "right now.</p></section>")
    h = d.get("history") or {}
    pending = h.get("windows_pending") or []
    body = "<section><h2>The ERA5 history behind this page</h2>"
    if pending:
        body += (f"<p>Loading: {len(pending)} decade window(s) of ERA5 data still to fetch "
                 f"({_e(', '.join(pending))}); {h.get('months') or 0} months stored so far. "
                 "Numbers that need a missing month are shown as n/a, never estimated.</p>")
    else:
        body += (f"<p>{h.get('months') or 0} months from {_e(h.get('from'))} to {_e(h.get('to'))}, "
                 f"ERA5 through {_e(h.get('last_day'))} (Open-Meteo archive, updated "
                 f"{_e(_fmt_dt(h.get('updated_at')))}).</p>")
    body += "</section>"
    tk = d.get("takeaways") or []
    if tk:
        body += ("<section><h2>Takeaways</h2><ol>" + "".join(f"<li>{_e(t)}</li>" for t in tk)
                 + "</ol></section>")
    cur = d.get("current_event") or {}
    base = (d.get("neutral_baseline") or {}).get("metrics") or {}

    def pk(x: dict | None) -> str:
        return f"{x['value']:+.2f} °C ({_e(x.get('season'))})" if x and x.get("value") is not None else "n/a"

    trs = ""
    for e in d.get("events") or []:
        s = e.get("samui") or {}
        trs += (f"<tr><td>{_e(e['id'])}</td><td>{pk(e.get('peak_oni'))}</td><td>{pk(e.get('peak_roni'))}"
                f"</td><td>{_e(e.get('strength') or 'n/a')}</td>"
                f"<td>{_n(s.get('ne_monsoon_rain_pct'), '%')}</td>"
                f"<td>{_n(s.get('dry_season_rain_pct'), '%')}</td>"
                f"<td>{_n(s.get('feb_apr_rain_pct'), '%')}</td>"
                f"<td>{_n(s.get('max_feels_like'), ' °C', 1)}"
                f"{' (' + _e(s['max_feels_like_day']) + ')' if s.get('max_feels_like_day') else ''}</td>"
                f"<td>{_n(s.get('heat_days'))}</td><td>{_n(s.get('longest_dry_spell_days'), ' d')}</td></tr>")
    nb = (d.get("neutral_baseline") or {})
    if base:
        trs += (f"<tr><td>Neutral years, median (n={nb.get('n')})</td><td></td><td></td><td>neutral</td>"
                f"<td>{_n(base.get('ne_monsoon_rain_pct', {}).get('median'), '%')}</td>"
                f"<td>{_n(base.get('dry_season_rain_pct', {}).get('median'), '%')}</td>"
                f"<td>{_n(base.get('feb_apr_rain_pct', {}).get('median'), '%')}</td>"
                f"<td>{_n(base.get('max_feels_like', {}).get('median'), ' °C', 1)}</td>"
                f"<td>{_n(base.get('heat_days', {}).get('median'))}</td>"
                f"<td>{_n(base.get('longest_dry_spell_days', {}).get('median'), ' d')}</td></tr>")
    so_far = cur.get("so_far") or {}
    sw = so_far.get("sw_monsoon") or {}
    trs += (f"<tr><td>{_e(cur.get('id'))} so far</td><td>{pk(cur.get('oni'))}</td><td>{pk(cur.get('roni'))}</td>"
            f"<td>{_e(cur.get('strength') or 'n/a')}</td><td colspan=\"6\">"
            + (f"Jun-Sep rain so far {_n(sw.get('rain_mm'), ' mm')}"
               + (f" = {_n(sw.get('pct'), '%')} of normal" if sw.get("pct") is not None else "")
               + f" (ERA5 through {_e(so_far.get('last_day'))})" if sw else "the season has not started")
            + "; Oct-Dec refill and the 2027 dry season are still ahead</td></tr>")
    body += ("<section><h2>Seven strong El Ninos vs 2026-27 (ERA5 cell, % of the 1991-2020 normal)</h2>"
             "<table><thead><tr><th>Event</th><th>Peak ONI</th><th>Peak RONI</th><th>Strength</th>"
             "<th>Oct-Dec rain</th><th>Jan-May rain</th><th>Feb-Apr rain</th><th>Max feels-like (Jan-May)</th>"
             "<th>Days &gt;= 39 °C feels-like</th><th>Longest dry spell (Jan-May)</th></tr></thead>"
             f"<tbody>{trs}</tbody></table></section>")
    imps = [i for e in (d.get("events") or []) for i in (e.get("impacts") or [])]
    imps += cur.get("impacts") or []
    imps += d.get("other_impacts") or []
    if imps:
        items = "".join(
            f"<li><b>{_e(i.get('date'))}</b> ({_e(i.get('type'))}, {_e(i.get('area'))}): {_e(i.get('text'))} "
            f"{_a(i['url'], i.get('source_title') or i.get('publisher') or 'source', True) if i.get('url') else ''}"
            f" [{_e(i.get('enso'))}]</li>" for i in sorted(imps, key=lambda x: str(x.get("date")), reverse=True))
        body += f"<section><h2>{len(imps)} documented impacts (each checked at its link)</h2><ul>{items}</ul></section>"
    nf = d.get("impacts_not_found") or []
    if nf:
        body += ("<section><h2>Looked for, not found</h2><ul>" + "".join(f"<li>{_e(x)}</li>" for x in nf)
                 + "</ul></section>")
    body += f"<section><h2>Method</h2><p>{_e(d.get('method'))}</p></section>"
    body += "<section><h2>ENSO status now</h2>" + _dl(_facts_rows(f)[:3]) + "</section>"
    return body


_SUMMARIES = {
    "/": _summary_overview, "/indices": _summary_indices, "/samui": _summary_samui,
    "/news": _summary_news, "/map": _summary_map, "/prep": _summary_prep,
    "/places": _summary_places, "/cams": _summary_cams, "/sources": _summary_sources,
    "/learn": _summary_learn, "/history": _summary_history,
}


# --------------------------------------------------------------------------- JSON-LD


def _org() -> dict:
    return {"@type": "Organization", "@id": settings.org_url.rstrip("/") + "/#org",
            "name": settings.org_name, "url": settings.org_url}


def _website() -> dict:
    return {"@type": "WebSite", "@id": absolute("/#website"), "url": absolute("/"),
            "name": settings.site_name, "inLanguage": "en",
            "description": ROUTES["/"]["description"], "publisher": {"@id": _org()["@id"]}}


def _breadcrumb(items: list[tuple[str, str]]) -> dict:
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": absolute(path)}
        for i, (path, name) in enumerate(items)]}


def _dataset_ld(d: dict, f: dict) -> dict:
    measured, first, last, latest_ts = [], None, None, None
    for source, series, name in d["series"]:
        v = f["series"].get(f"{source}/{series}") or _latest(source, series)
        rng = db.query("SELECT MIN(ts) AS a, MAX(ts) AS b FROM observations WHERE source=? AND series=?",
                       (source, series))
        if rng and rng[0]["a"]:
            first = min(first or rng[0]["a"], rng[0]["a"])
            last = max(last or rng[0]["b"], rng[0]["b"])
        pv: dict = {"@type": "PropertyValue", "name": name}
        if v and v["value"] is not None:
            pv["value"] = v["value"]
            pv["unitText"] = v.get("unit") or ""
            pv["description"] = f"latest value, {v['ts'][:10]}"
            latest_ts = max(latest_ts or v["ts"], v["ts"])
        measured.append(pv)
    if d.get("point"):
        spatial: dict = {"@type": "Place", "name": settings.home_name, "geo": {
            "@type": "GeoCoordinates", "latitude": settings.home_lat,
            "longitude": settings.home_lon}}
    else:
        spatial = {"@type": "Place", "geo": {"@type": "GeoShape", "box": d["box"]}}
    out = {
        "@type": "Dataset", "@id": absolute(f"/indices#dataset-{d['id']}"),
        "name": d["name"], "description": d["description"],
        "url": absolute(d.get("page") or ("/samui" if d.get("point") else "/indices")),
        "keywords": d["keywords"], "inLanguage": "en", "isAccessibleForFree": True,
        "creator": {"@type": "Organization", "name": d["provider"]},
        "provider": {"@type": "Organization", "name": d["provider"]},
        "publisher": {"@id": _org()["@id"]},
        "isBasedOn": d["isBasedOn"], "license": d["license"],
        "conditionsOfAccess": d["license_note"],
        "spatialCoverage": spatial, "variableMeasured": measured,
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "name": f"{name} (JSON, oldest to newest)",
             "contentUrl": absolute(f"/api/series?source={source}&series={series}")}
            for source, series, name in d["series"]] + [
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "name": "Latest value of every series", "contentUrl": absolute("/api/latest")}],
    }
    if first and last:
        out["temporalCoverage"] = f"{first[:10]}/{last[:10]}"
    if latest_ts:
        out["dateModified"] = latest_ts[:10]
    return out


def _faq_ld() -> dict | None:
    items = learn_content()["faq"]
    if not items:
        return None
    return {"@type": "FAQPage", "@id": absolute("/learn#faq"), "mainEntity": [
        {"@type": "Question", "name": q["question"], "url": absolute(f"/learn#faq-{q['id']}"),
         "acceptedAnswer": {"@type": "Answer", "text": q["answer_text"]}} for q in items]}


def json_ld(path: str, meta: dict, f: dict, topic: dict | None = None) -> dict:
    page: dict = {
        "@type": "WebPage", "@id": absolute(path) + "#webpage", "url": absolute(path),
        "name": meta["title"], "description": meta["description"], "inLanguage": "en",
        "isPartOf": {"@id": absolute("/#website")},
        "about": {"@type": "Thing", "name": "El Nino 2026-27 (ENSO warm phase)"},
    }
    if f["updated_at"]:
        page["dateModified"] = f["updated_at"]
    crumbs = [("/", "El Nino Watch")]
    if path.startswith("/learn/") and topic:
        crumbs += [("/learn", "Learn"), (path, topic["title"])]
    elif path != "/":
        crumbs.append((path, meta["name"]))
    page["breadcrumb"] = {"@id": absolute(path) + "#breadcrumb"}
    graph: list[dict] = [_org(), _website(), page,
                         _breadcrumb(crumbs) | {"@id": absolute(path) + "#breadcrumb"}]
    if path in ("/", "/indices"):
        graph += [_dataset_ld(d, f) for d in DATASETS if not d.get("point")]
    if path in ("/", "/samui"):
        graph += [_dataset_ld(d, f) for d in DATASETS if d.get("point") and not d.get("page")]
        lv = f["local"]
        if lv:
            graph.append({"@type": "Place", "@id": absolute("/samui#place"),
                          "name": "Koh Samui, Surat Thani, Thailand",
                          "geo": {"@type": "GeoCoordinates", "latitude": settings.home_lat,
                                  "longitude": settings.home_lon}})
    graph += [_dataset_ld(d, f) for d in DATASETS if d.get("page") == path]
    if path == "/learn":
        faq = _faq_ld()
        if faq:
            graph.append(faq)
    if topic:
        lc = learn_content()
        art: dict = {"@type": "TechArticle", "@id": absolute(path) + "#article",
                     "headline": topic["title"], "description": topic["short"],
                     "articleSection": topic["category_label"], "inLanguage": "en",
                     "isAccessibleForFree": True, "mainEntityOfPage": {"@id": page["@id"]},
                     "author": {"@id": _org()["@id"]}, "publisher": {"@id": _org()["@id"]},
                     "citation": [s["url"] for s in topic.get("sources", [])]}
        if lc["generated_at"]:
            art["dateModified"] = lc["generated_at"][:10]
        graph.append(art)
    return {"@context": "https://schema.org", "@graph": graph}


# --------------------------------------------------------------------------- page render

_TITLE = re.compile(r"<title>.*?</title>", re.DOTALL | re.IGNORECASE)
_DESC = re.compile(r'\s*<meta name="description"[^>]*>', re.IGNORECASE)
_HEAD_MARK = "<!--seo:head-->"
_ROOT = re.compile(r'<div id="root">\s*</div>', re.IGNORECASE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FALLBACK_TEMPLATE = (
    '<!doctype html><html lang="en" data-theme="dark"><head><meta charset="UTF-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    '<title>El Nino Watch</title></head><body><div id="root"></div></body></html>')


def _template() -> tuple[str, bool]:
    """dist/index.html without its HTML comments: a comment that mentions <title> or
    <meta> would otherwise be matched by the injection regexes and, once cut open,
    swallow the rest of the page (browsers parse comments, curl does not)."""
    index = DIST / "index.html"
    if index.is_file():
        return _COMMENT.sub("", index.read_text(encoding="utf-8")), True
    return _FALLBACK_TEMPLATE, False


def _sha(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"


def csp_with(extra_hashes: list[str]) -> str:
    """security.py's policy plus the hashes of the scripts injected into this response."""
    parts = []
    for directive, sources in security.CSP_SOURCES.items():
        if directive == "script-src":
            sources = sources + security.inline_script_hashes() + extra_hashes
        parts.append(f"{directive} {' '.join(sources)}")
    return "; ".join(parts)


def route_map() -> dict:
    """What the frontend `useSeo` hook reads from <script id="seo-routes"> on navigation."""
    return {"origin": origin(), "site_name": settings.site_name,
            "og_image": absolute("/og/current.png"),
            "routes": {p: {"title": m["title"], "description": m["description"]}
                       for p, m in ROUTES.items()}}


def head_tags(path: str, meta: dict, image_alt: str, robots: str = "index,follow") -> str:
    url = absolute(path)
    og = absolute("/og/current.png")
    tags = [
        f'<title>{_e(meta["title"])}</title>',
        f'<meta name="description" content="{_e(meta["description"])}">',
        f'<meta name="robots" content="{robots},max-image-preview:large">',
        f'<link rel="canonical" href="{_e(url)}">',
        f'<link rel="alternate" hreflang="en" href="{_e(url)}">',
        f'<link rel="alternate" hreflang="x-default" href="{_e(url)}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{_e(settings.site_name)}">',
        '<meta property="og:locale" content="en_US">',
        f'<meta property="og:title" content="{_e(meta["title"])}">',
        f'<meta property="og:description" content="{_e(meta["description"])}">',
        f'<meta property="og:url" content="{_e(url)}">',
        f'<meta property="og:image" content="{_e(og)}">',
        '<meta property="og:image:type" content="image/png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{_e(image_alt)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{_e(meta["title"])}">',
        f'<meta name="twitter:description" content="{_e(meta["description"])}">',
        f'<meta name="twitter:image" content="{_e(og)}">',
        f'<meta name="twitter:image:alt" content="{_e(image_alt)}">',
    ]
    if settings.google_site_verification:
        tags.append(f'<meta name="google-site-verification" '
                    f'content="{_e(settings.google_site_verification)}">')
    if settings.bing_site_verification:
        tags.append(f'<meta name="msvalidate.01" content="{_e(settings.bing_site_verification)}">')
    return "\n    ".join(tags)


def topic_meta(t: dict) -> dict:
    title = _fit(f"{t['title']}: El Nino explained", TITLE_MAX)
    if len(title) > TITLE_MAX:
        title = _fit(t["title"], TITLE_MAX)
    desc = t["short"]
    if len(desc) < DESC_MIN and t.get("body"):
        desc = desc + " " + t["body"].split("\n")[0]
    return {"name": t["title"], "title": title, "description": _fit(desc, DESC_MAX)}


def render(path: str, topic: dict | None = None, robots: str = "index,follow") -> tuple[str, list[str]]:
    """The HTML for one route + the CSP hashes of the scripts injected into it."""
    f = facts()
    meta = topic_meta(topic) if topic else ROUTES[path]
    phrase = enso_phrase(f)
    image_alt = f"El Nino Watch: {phrase}" if phrase else "El Nino Watch live status card"
    ld = json.dumps(json_ld(path, meta, f, topic), ensure_ascii=False, separators=(",", ":"))
    ld = ld.replace("</", "<\\/")
    rm = json.dumps(route_map(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    scripts = [f'<script type="application/ld+json" data-path="{_e(path)}">{ld}</script>',
               f'<script type="application/json" id="seo-routes">{rm}</script>']
    hashes = [_sha(ld), _sha(rm)]
    head = head_tags(path, meta, image_alt, robots) + "\n    " + "\n    ".join(scripts)

    html, built = _template()
    html = _DESC.sub("", html)
    if _TITLE.search(html):
        html = _TITLE.sub(lambda _m: head, html, count=1)
    else:
        html = html.replace("</head>", head + "\n</head>", 1)
    html = html.replace(_HEAD_MARK, "", 1)
    if topic:
        summary = _summary_shell(path, topic["title"], topic["short"], _summary_topic(topic, f), f)
    else:
        summary = _summary_shell(path, meta["title"], meta["description"],
                                 _SUMMARIES[path](f), f)
    html, n = _ROOT.subn(lambda _m: f'<div id="root">{summary}</div>', html, count=1)
    if not n:
        html = html.replace("<body>", f"<body>{summary}", 1)
    if not built:
        log.warning("seo: frontend/dist/index.html missing, serving the bare summary")
    return html, hashes


def _html_response(html: str, hashes: list[str], status: int = 200) -> HTMLResponse:
    headers = {"Cache-Control": "no-cache", "Vary": "Accept-Encoding"}
    if settings.public_mode:
        headers["Content-Security-Policy"] = csp_with(hashes)
    return HTMLResponse(html, status_code=status, headers=headers)


# --------------------------------------------------------------------------- routes: pages


def _page(path: str):
    def handler() -> HTMLResponse:
        html, hashes = render(path)
        return _html_response(html, hashes)
    handler.__name__ = "seo_page_" + (path.strip("/") or "home")
    return handler


def _redirect(target: str):
    def handler() -> RedirectResponse:
        return RedirectResponse(target, status_code=301)
    handler.__name__ = "seo_redirect_" + target.strip("/")
    return handler


for _path in ROUTES:
    router.add_api_route(_path, _page(_path), methods=["GET"], include_in_schema=False,
                         response_class=HTMLResponse)
    if _path != "/":  # trailing-slash duplicate -> the canonical URL
        router.add_api_route(_path + "/", _redirect(_path), methods=["GET"],
                             include_in_schema=False)

for _old, _new in LEGACY_REDIRECTS.items():
    router.add_api_route(_old, _redirect(_new), methods=["GET"], include_in_schema=False)


@router.get("/learn/{topic_id}", include_in_schema=False, response_class=HTMLResponse)
def learn_topic(topic_id: str) -> HTMLResponse:
    t = learn_content()["topics"].get(topic_id)
    if t is None:
        # unknown topic: the SPA's Learn page with a 404 status and noindex (no soft 404)
        html, hashes = render("/learn", robots="noindex,follow")
        return _html_response(html, hashes, status=404)
    html, hashes = render(f"/learn/{topic_id}", topic=t)
    return _html_response(html, hashes)


# --------------------------------------------------------------------------- robots / sitemap

ROBOTS_ALLOWED_API = ("/api/latest", "/api/series", "/api/status", "/api/local",
                      "/api/local/weather", "/api/sources")


@router.get("/robots.txt", include_in_schema=False)
def robots_txt() -> Response:
    """Allow everything a person can open; keep crawlers out of /api/ except the handful
    of JSON endpoints referenced as Dataset distributions (cheap, cacheable, documented).
    The rest of /api/ is parameterised JSON that would only burn crawl budget and CPU."""
    lines = ["User-agent: *", "Allow: /"]
    lines += [f"Allow: {p}" for p in ROBOTS_ALLOWED_API]
    lines += ["Disallow: /api/", "Disallow: /docs", "Disallow: /redoc", "Disallow: /openapi.json",
              "", f"Sitemap: {absolute('/sitemap.xml')}", ""]
    return Response("\n".join(lines), media_type="text/plain",
                    headers={"Cache-Control": "public, max-age=3600"})


def _max(sql: str, params: tuple = ()) -> str | None:
    rows = db.query(sql, params)
    return rows[0]["t"] if rows and rows[0].get("t") else None


def lastmods() -> dict[str, str | None]:
    """Route -> ISO date of the last real content change (never a fake 'now')."""
    st = {r["key"]: r["updated_at"] for r in db.query("SELECT key, updated_at FROM status")}
    idx = tuple(s["source"] for s in INDEX_SERIES)
    lc = learn_content()
    build = lc["generated_at"]
    index = DIST / "index.html"
    if index.is_file():
        built = datetime.fromtimestamp(index.stat().st_mtime, UTC).isoformat()
        build = max(build or built, built)
    out = {
        "/": max(filter(None, [st.get("cpc_alert"), st.get("iri_plume"), st.get("local_risk"),
                               st.get("briefing")]), default=None),
        "/indices": _max("SELECT MAX(finished_at) AS t FROM source_runs WHERE ok=1 AND source IN "
                         f"({','.join('?' * len(idx))})", idx),
        "/samui": st.get("local_risk"),
        "/history": st.get("samui_era5_history"),
        "/news": _max("SELECT MAX(COALESCE(published_at, fetched_at)) AS t FROM feed_items"),
        "/map": _max("SELECT MAX(COALESCE(updated_at, started_at)) AS t FROM events"),
        "/sources": _max("SELECT MAX(finished_at) AS t FROM source_runs"),
        "/cams": st.get("webcams"),
        "/places": _max("SELECT MAX(updated_at) AS t FROM status WHERE key LIKE 'place%'"),
        "/prep": build, "/learn": build,
    }
    return {k: _iso_date(v) for k, v in out.items()}


_sitemap_cache: tuple[float, str] | None = None


def sitemap_xml(force: bool = False) -> str:
    global _sitemap_cache
    if not force and _sitemap_cache and time.monotonic() - _sitemap_cache[0] < SITEMAP_TTL_S:
        return _sitemap_cache[1]
    lm = lastmods()
    lc = learn_content()
    entries: list[tuple[str, str | None, str, str]] = []
    prio = {"/": "1.0", "/samui": "0.9", "/indices": "0.9", "/learn": "0.8", "/map": "0.8",
            "/history": "0.8", "/news": "0.7", "/prep": "0.7", "/places": "0.6", "/cams": "0.5",
            "/sources": "0.5"}
    freq = {"/": "hourly", "/indices": "daily", "/samui": "hourly", "/news": "hourly",
            "/map": "hourly", "/sources": "daily", "/history": "daily"}
    for p in ROUTES:
        entries.append((absolute(p), lm.get(p), freq.get(p, "weekly"), prio.get(p, "0.5")))
    for tid in sorted(lc["topics"]):
        entries.append((absolute(f"/learn/{tid}"), lm.get("/learn"), "monthly", "0.6"))
    body = "".join(
        f"<url><loc>{_e(loc)}</loc>" + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
        + f"<changefreq>{cf}</changefreq><priority>{pr}</priority></url>"
        for loc, lastmod, cf, pr in entries)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + body + "</urlset>\n")
    _sitemap_cache = (time.monotonic(), xml)
    return xml


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap() -> Response:
    return Response(sitemap_xml(), media_type="application/xml",
                    headers={"Cache-Control": "public, max-age=300"})


# --------------------------------------------------------------------------- IndexNow


def indexnow_enabled() -> bool:
    key = settings.indexnow_key
    host = origin().split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    if not key or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", key):
        return False
    return not any(host.endswith(s) for s in DISPOSABLE_HOST_SUFFIXES)


@router.get("/{name}.txt", include_in_schema=False)
def key_file(name: str) -> Response:
    """The IndexNow key file (/<key>.txt must answer the key); other .txt come from dist."""
    if settings.indexnow_key and name == settings.indexnow_key:
        return Response(name, media_type="text/plain")
    f = DIST / f"{name}.txt"
    if f.is_file() and f.resolve().is_relative_to(DIST.resolve()):
        return FileResponse(f)
    raise HTTPException(404, "Not Found")


async def indexnow_ping(urls: list[str], client: httpx.AsyncClient | None = None) -> dict:
    """Submit changed URLs to IndexNow (one call reaches Bing, Yandex, Seznam, Naver...).
    Returns {sent, status} or {sent: 0, reason} when disabled. Never raises."""
    if not indexnow_enabled():
        return {"sent": 0, "reason": "disabled (no key, or PUBLIC_ORIGIN is a disposable host)"}
    urls = [u for u in urls if u.startswith(origin())][:10000]
    if not urls:
        return {"sent": 0, "reason": "no URLs on the canonical origin"}
    host = origin().split("://", 1)[-1]
    payload = {"host": host, "key": settings.indexnow_key,
               "keyLocation": absolute(f"/{settings.indexnow_key}.txt"), "urlList": urls}
    try:
        own = client is None
        client = client or httpx.AsyncClient(timeout=15.0, headers={"User-Agent": settings.user_agent})
        try:
            r = await client.post(INDEXNOW_ENDPOINT, json=payload)
        finally:
            if own:
                await client.aclose()
        log.info("indexnow: %d URLs -> HTTP %d", len(urls), r.status_code)
        return {"sent": len(urls), "status": r.status_code}
    except httpx.HTTPError as e:
        log.warning("indexnow: ping failed: %s", e)
        return {"sent": 0, "reason": str(e)}


_last_lastmods: dict[str, str | None] | None = None


async def indexnow_post_hook() -> None:
    """After every collector round: if a route's lastmod moved, tell IndexNow (when enabled)."""
    global _last_lastmods
    invalidate_caches()
    if not indexnow_enabled():
        return
    now = lastmods()
    if _last_lastmods is not None:
        changed = [absolute(p) for p, d in now.items() if d and d != _last_lastmods.get(p)]
        if changed:
            await indexnow_ping(changed + [absolute("/sitemap.xml")])
    _last_lastmods = now


scheduler.register_post_hook(indexnow_post_hook)


# --------------------------------------------------------------------------- Open Graph image

_og_cache: tuple[float, str | None, bytes] | None = None
BG, INK, INK2, INK3 = (7, 17, 31), (240, 244, 250), (170, 182, 200), (110, 122, 140)
BLUE, RED, AMBER, GREEN = (59, 139, 234), (229, 72, 77), (245, 158, 11), (34, 197, 94)
LEVEL_COLOR = {"normal": GREEN, "vigilance": AMBER, "prepare": AMBER, "act": RED, "leave": RED,
               "unknown": INK3}


def _ascii(text: str) -> str:
    """The bundled Pillow font has no accented glyphs: 'El Niño' -> 'El Nino' (keeps °)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow: bitmap font only
        return ImageFont.load_default()


def _wave(draw, y: int, x0: int, x1: int, amp: int, color, width: int = 6) -> None:
    import math
    pts = [(x, y + amp * math.sin((x - x0) / (x1 - x0) * math.tau)) for x in range(x0, x1 + 1, 4)]
    draw.line(pts, fill=color, width=width, joint="curve")


def og_png(f: dict | None = None) -> bytes:
    """1200x630 status card. Pure Pillow, no fonts from the system, ~1 MB of RAM."""
    from PIL import Image, ImageDraw
    f = f or facts()
    im = Image.new("RGB", (1200, 630), BG)
    raw = ImageDraw.Draw(im)

    class _D:  # every text() call ASCII-folded, everything else passed through
        def text(self, xy, txt, **kw):
            raw.text(xy, _ascii(txt), **kw)

        def __getattr__(self, name):
            return getattr(raw, name)

    d = _D()
    d.rectangle((0, 0, 14, 630), fill=BLUE)
    _wave(d, 78, 60, 150, 10, BLUE)
    _wave(d, 100, 60, 150, 10, RED)
    d.text((176, 58), settings.site_name, fill=INK, font=_font(44))
    host = origin().split("://", 1)[-1]
    d.text((176, 108), host, fill=INK3, font=_font(24))
    d.text((60, 172), "El Nino 2026-27: live tracker", fill=INK2, font=_font(34))

    tiles = [("ONI", f["oni"], 2, "3-month, NOAA CPC"), ("RONI", f["roni"], 2, "relative ONI"),
             ("Nino 3.4", f["nino34"], 1, "weekly anomaly")]
    x = 60
    for label, v, dec, sub in tiles:
        d.rounded_rectangle((x, 236, x + 340, 402), radius=18, fill=(12, 26, 46),
                            outline=(30, 48, 74), width=2)
        d.text((x + 24, 254), label, fill=INK3, font=_font(26))
        if v and v["value"] is not None:
            val = f"{v['value']:+.{dec}f} °C"
            when = _season_code(v["ts"]) if label != "Nino 3.4" else f"wk of {_fmt_day(v['ts'])}"
            col = RED if v["value"] >= 0.5 else BLUE if v["value"] <= -0.5 else INK
        else:
            val, when, col = "n/a", "no data", INK3
        d.text((x + 24, 290), val, fill=col, font=_font(64))
        d.text((x + 24, 364), f"{when} · {sub}", fill=INK3, font=_font(20))
        x += 360

    y = 436
    cpc = f["cpc"]
    if cpc and cpc.get("status"):
        txt = f"NOAA CPC: {cpc['status']} (issued {_fmt_day(cpc.get('issued'))})"
    else:
        txt = "NOAA CPC status: no data"
    d.text((60, y), txt, fill=INK, font=_font(30))
    lv = f["local"]
    y += 48
    if lv and lv.get("level_key"):
        label = lv.get("level_label") or lv["level_key"]
        col = LEVEL_COLOR.get(lv["level_key"], INK3)
        d.ellipse((60, y + 8, 84, y + 32), fill=col)
        d.text((98, y), f"Koh Samui, Thailand: {label}", fill=INK, font=_font(30))
    else:
        d.text((60, y), "Koh Samui, Thailand: no evaluation yet", fill=INK3, font=_font(30))
    d.text((60, 578), f"Data as of {_fmt_dt(f['updated_at'])} · sources: NOAA CPC, IRI, BoM, TMD, "
           f"Open-Meteo · {settings.org_name}", fill=INK3, font=_font(20))
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@router.get("/og/current.png", include_in_schema=False)
def og_current(request: Request) -> Response:
    global _og_cache
    f = facts()
    key = f["updated_at"]
    if not (_og_cache and _og_cache[1] == key and time.monotonic() - _og_cache[0] < OG_TTL_S):
        try:
            png = og_png(f)
        except ImportError:
            fallback = DIST / "og-default.png"
            if fallback.is_file():
                return FileResponse(fallback, media_type="image/png")
            raise HTTPException(503, "Pillow is not installed") from None
        _og_cache = (time.monotonic(), key, png)
    png = _og_cache[2]
    etag = '"' + hashlib.sha256(png).hexdigest()[:16] + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(png, media_type="image/png",
                    headers={"Cache-Control": f"public, max-age={int(OG_TTL_S)}", "ETag": etag})
