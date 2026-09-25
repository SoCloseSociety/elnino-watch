"""Extra Thailand / Koh Samui sources (gap fill, 2026-09-24).

- air4thai_south        Thai Pollution Control Department (PCD) Air4Thai: MEASURED PM2.5,
                        PM10 and Thai AQI at the ground stations within 300 km of home
                        (Surat Thani, Nakhon Si Thammarat, Chumphon, ...). Complements the
                        CAMS model in openmeteo_samui_air. Status `air4thai_samui`.
- asmc_seasonal_outlook ASEAN Specialised Meteorological Centre seasonal outlook for SE Asia
                        (rainfall / temperature / haze), monthly. Status + official feed.
"""

from __future__ import annotations

import html
import re
import ssl
from datetime import UTC, datetime

import certifi
import httpx

from .. import db
from ..config import settings
from .base import DAY, HOUR, Collector, RunContext, SourceChanged
from .extra_hazards import home_km
from .extra_ocean import MONTH_NAMES, set_status_if_changed, store_obs

# ------------------------------------------------------------------ Air4Thai

AIR4THAI_URL = "https://air4thai.pcd.go.th/services/getNewAQI_JSON.php"
AIR4THAI_PAGE = "https://air4thai.pcd.go.th/webV3/"
AIR4THAI_RADIUS_KM = 300.0
# air4thai.pcd.go.th serves a Let's Encrypt leaf (issuer YR1) with an unrelated Sectigo chain,
# so strict clients (Python/OpenSSL + certifi) cannot build the path. We add the two missing
# PUBLIC Let's Encrypt intermediates (fetched from the leaf's AIA URLs on 2026-09-24:
# http://yr1.i.lencr.org/ "YR1", and http://yr.i.lencr.org/ "Root YR" cross-signed by
# ISRG Root X1, which certifi trusts). Verification stays fully on; nothing is disabled.
LE_YR_CHAIN = """
-----BEGIN CERTIFICATE-----
MIIE2zCCAsOgAwIBAgIRAKICU/FfJpHAXcHOE7m8yk4wDQYJKoZIhvcNAQELBQAw
LjELMAkGA1UEBhMCVVMxDTALBgNVBAoTBElTUkcxEDAOBgNVBAMTB1Jvb3QgWVIw
HhcNMjUwOTAzMDAwMDAwWhcNMjgwOTAyMjM1OTU5WjAzMQswCQYDVQQGEwJVUzEW
MBQGA1UEChMNTGV0J3MgRW5jcnlwdDEMMAoGA1UEAxMDWVIxMIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoVi8X2xCYgMXvJxNPKp/oF13UMgmPABB07VC
LNDtoXmt9luEZNJSBV10VyT1Pz6LD8Zq1d2gc43WNl1AdRrj4sEnazbOiz0nPpmG
Bp2hui49oZtDIY6wdKeZAi5BbNU20CH6RSBBMLSQ9cXrH8dxdv4PAJ45ssGML68U
SE3BsjC2a6cAN9L5CgXVIQi5tfNiTPoFZZ3S0OlXqLmmtdV95udWAb5b6e/F49Di
CsH0Y00Ag72BVIb1hzynmKe+X0mERBTtsb3BwmpV9ipeBjMLoR/D9cHxHQCWoi5l
TmXwY015J5rGelz1nZjJuxc2kioaX29XJBnhMkP531rSdG5uMwIDAQABo4HuMIHr
MA4GA1UdDwEB/wQEAwIBhjATBgNVHSUEDDAKBggrBgEFBQcDATASBgNVHRMBAf8E
CDAGAQH/AgEAMB0GA1UdDgQWBBQfLzW+RhSCzUCxrnksVXj699Ro+zAfBgNVHSME
GDAWgBTe51tg0CJtQCh9Pw0B/qS1UrRRlDAyBggrBgEFBQcBAQQmMCQwIgYIKwYB
BQUHMAKGFmh0dHA6Ly95ci5pLmxlbmNyLm9yZy8wEwYDVR0gBAwwCjAIBgZngQwB
AgEwJwYDVR0fBCAwHjAcoBqgGIYWaHR0cDovL3lyLmMubGVuY3Iub3JnLzANBgkq
hkiG9w0BAQsFAAOCAgEA0+zvMq3kHig1ddTmmm+RibTr9/RpX7k4buanMMRqbV/y
IvP82zAHN3mvaw+cASuVsdpd0ikjhr4hnhJQLQOzOp2ccKrsdGOAgo0vddeISFAq
EWEV4lmUM3vFF796up+bSgmJ1u6RupDCMxDgF8M3eLvGuj6L0lu3zkQ0KuQLnKxL
tB0oQqn1Idg5CuuGpMvQzk29Pa3D/qHurc0EIM9SxukQuJqq63lxsYyRQFU8yMBO
hq1w5LbfaWNRrz1uklOfI/pYkAb2E2MTZrAMQkBIE2S8Jt1F8gRc96o/xOsrgvSk
a84AisX6xq1lz1Z7jGvrnXc4TMcjxZTjiTaihcYI1JIXZiLtEMSCa5l3cu8YWd6z
dLRQlqRdclVjuQfNHawRJ6GWlkK0QJosivTKwdBw3KxEtzGo8yMHERbsy57gP1UX
HOMcmZYQC0gtyR3SxfenIM/MxC3Ia2Ypab/kQ/CTnlIn2KQ5JUC6NYrGCbhFN9bp
5lKJStEwCUnLpntcrXk5XVDCNv/5RyWpRThkGOV7GetKkQ0qAY8hCzWK6oqnAhDZ
cjlYVdWfqOw3DIOX6EDNBgAqHarRVxyF9QZdOaXSyPJ0ueD2BYJEBgaCGQ8rAaU/
Qc123V5LTXDZW4CcsPBDyhy4v+c8hClAyw/IkJlfBqxB9D+/wvIMHgECZ4ptP6o=
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
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
-----END CERTIFICATE-----
"""


def air4thai_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_verify_locations(cadata=LE_YR_CHAIN)
    return ctx
# Thai AQI bands (PCD): upper bound -> (key, label)
THAI_AQI = (
    (25, "very_good", "Very good"),
    (50, "good", "Good"),
    (100, "moderate", "Moderate"),
    (200, "unhealthy", "Starting to affect health"),
    (10**9, "very_unhealthy", "Affects health"),
)


def thai_aqi_band(aqi: float | None) -> tuple[str, str] | tuple[None, None]:
    if aqi is None or aqi < 0:
        return None, None
    for top, key, label in THAI_AQI:
        if aqi <= top:
            return key, label
    return None, None


def _num(cell: dict | None, key: str = "value") -> float | None:
    try:
        v = float((cell or {}).get(key))
    except (TypeError, ValueError):
        return None
    return None if v < 0 else v  # -1 = not measured at this station


def parse_air4thai(payload: dict, radius_km: float = AIR4THAI_RADIUS_KM) -> tuple[list, list]:
    """-> (observation rows, station summaries sorted by distance)."""
    st = payload.get("stations") if isinstance(payload, dict) else None
    if not isinstance(st, list) or not st:
        raise SourceChanged("Air4Thai: no 'stations' list")
    rows, stations = [], []
    for s in st:
        try:
            lat, lon = float(s["lat"]), float(s["long"])
        except (KeyError, TypeError, ValueError):
            continue
        d = home_km(lat, lon)
        if d > radius_km:
            continue
        last = s.get("AQILast") or {}
        if not last.get("date") or not last.get("time"):
            continue
        try:
            t = datetime.strptime(f"{last['date']} {last['time']} +0700", "%Y-%m-%d %H:%M %z")
        except ValueError:
            raise SourceChanged(
                f"Air4Thai: odd timestamp {last.get('date')} {last.get('time')}") from None
        ts = t.astimezone(UTC).isoformat()
        sid = re.sub(r"[^a-z0-9]", "", str(s.get("stationID", "")).lower())
        pm25, pm10 = _num(last.get("PM25")), _num(last.get("PM10"))
        aqi = _num(last.get("AQI"), "aqi")
        meta = {"station": s.get("stationID"), "name": s.get("nameEN"), "area": s.get("areaEN"),
                "distance_km": d}
        for key, v, unit in (("pm25", pm25, "ug/m3"), ("pm10", pm10, "ug/m3"),
                             ("aqi", aqi, "Thai AQI")):
            if v is not None:
                rows.append({"series": f"air4thai_{sid}_{key}", "ts": ts, "value": v,
                             "unit": unit, "meta": meta})
        band, label = thai_aqi_band(aqi)
        stations.append({"station": s.get("stationID"), "name": s.get("nameEN"),
                         "area": s.get("areaEN"), "lat": lat, "lon": lon, "distance_km": d,
                         "observed_at": ts, "pm25": pm25, "pm10": pm10, "aqi": aqi,
                         "aqi_param": (last.get("AQI") or {}).get("param"),
                         "band": band, "band_label": label,
                         "series_prefix": f"air4thai_{sid}"})
    if not stations:
        raise SourceChanged(f"Air4Thai: no station within {radius_km:.0f} km of home")
    stations.sort(key=lambda x: x["distance_km"])
    return rows, stations


class Air4ThaiSouth(Collector):
    name = "air4thai_south"
    title = "Air4Thai -- measured PM2.5 / AQI, southern Thailand stations"
    category = "local"
    provider = "Pollution Control Department (PCD), Thailand"
    homepage = AIR4THAI_PAGE
    endpoint = AIR4THAI_URL
    interval_s = HOUR
    freshness_basis = "observations"
    max_age_s = 6 * HOUR
    description = ("Hourly MEASURED air quality from the Thai government ground stations within "
                   "300 km of Koh Samui (nearest: Surat Thani, ~87 km). Koh Samui itself has no "
                   "PCD station. Series air4thai_<station>_pm25 / _pm10 (ug/m3) / _aqi (Thai AQI: "
                   "0-25 very good, 26-50 good, 51-100 moderate, 101-200 starting to affect "
                   "health, >200 affects health). Status key `air4thai_samui` = nearest station.")

    async def collect(self, ctx: RunContext) -> int:
        async with httpx.AsyncClient(verify=air4thai_ssl_context(), follow_redirects=True,
                                     timeout=httpx.Timeout(30.0, connect=10.0),
                                     headers={"User-Agent": settings.user_agent}) as c:
            r = await c.get(AIR4THAI_URL)
        ctx.last_status = r.status_code
        r.raise_for_status()
        rows, stations = parse_air4thai(r.json())
        nearest = stations[0]
        db.set_status("air4thai_samui", {**nearest, "url": AIR4THAI_PAGE,
                                          "stations": stations,
                                          "note": "Nearest PCD station; Koh Samui has none."})
        ctx.notes["nearest"] = f"{nearest['name']} {nearest['pm25']} ug/m3 at {nearest['observed_at']}"
        return store_obs(self.name, rows, ctx)


# ------------------------------------------------------------------ ASMC seasonal outlook

ASMC_OUTLOOK_URL = "https://asmc.asean.org/asmc-seasonal-outlook/"
_H2 = re.compile(r"<h2>\s*(Seasonal Forecast for[^<]+)</h2>")
_UPDATED = re.compile(r"Updated\s+(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")
_P = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)
_PANEL = re.compile(r'<div class="panel-title float-start">(.*?)</div>', re.DOTALL)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).replace(
        "\xa0", " ").strip()


def parse_asmc_outlook(page: str) -> dict:
    h = _H2.search(page)
    u = _UPDATED.search(page[h.end():h.end() + 400]) if h else None
    if not h or not u or u.group(2) not in MONTH_NAMES:
        raise SourceChanged("ASMC outlook: no 'Seasonal Forecast for ...' / 'Updated <date>'")
    updated = f"{int(u.group(3)):04d}-{MONTH_NAMES[u.group(2)]:02d}-{int(u.group(1)):02d}"
    body = page[h.end():]
    end = body.find("Frequently Asked Questions")
    body = body[:end] if end > 0 else body
    paras = [_clean(p) for p in _P.findall(body)]
    paras = [p for p in paras if len(p) > 40]
    if len(paras) < 2:
        raise SourceChanged("ASMC outlook: no paragraphs")
    overview = [p for p in paras if not p.startswith("Updated")][:3]
    mainland = [p for p in paras if "Mainland Southeast Asia" in p][:4]
    sections = [_clean(x) for x in _PANEL.findall(body)]
    sections = [x for x in sections if x]
    images = sorted(set(re.findall(
        r"https://asmc\.asean\.org/wp-content/uploads/[^\"'\s>]+\.(?:jpe?g|png)", body)))
    return {"title": _clean(h.group(1)), "updated": updated, "overview": overview,
            "mainland_sea": mainland, "sections": sections, "images": images[:12],
            "url": ASMC_OUTLOOK_URL}


class AsmcSeasonalOutlook(Collector):
    name = "asmc_seasonal_outlook"
    title = "ASMC -- ASEAN seasonal outlook (rain, temperature, haze)"
    category = "official"
    provider = "ASEAN Specialised Meteorological Centre (ASMC)"
    homepage = ASMC_OUTLOOK_URL
    endpoint = ASMC_OUTLOOK_URL
    interval_s = 12 * HOUR
    freshness_basis = "feed"
    max_age_s = 40 * DAY  # monthly, early in the month
    description = ("The WMO Regional Climate Centre for South-East Asia: monthly and 3-month "
                   "outlook of rainfall and temperature for the ASEAN region (multi-model), with "
                   "the El Nino context and the haze risk. Status key `asmc_seasonal_outlook`, "
                   "one official feed item per issue.")

    async def collect(self, ctx: RunContext) -> int:
        doc = parse_asmc_outlook((await ctx.get(ASMC_OUTLOOK_URL)).text)
        set_status_if_changed("asmc_seasonal_outlook", doc)
        summary = " ".join(doc["overview"])[:1000]
        text = " ".join([doc["title"], *doc["overview"], *doc["mainland_sea"]])
        tags = ["asean"]
        if re.search(r"El Ni", text):
            tags.append("enso")
        if re.search(r"haze", text, re.IGNORECASE):
            tags.append("haze")
        db.upsert_feed_items(self.name, [{
            "ext_id": doc["updated"], "kind": "official", "title": f"ASMC {doc['title']}",
            "summary": summary, "url": ASMC_OUTLOOK_URL, "author": "ASMC", "lang": "en",
            "published_at": f"{doc['updated']}T00:00:00+00:00", "tags": tags,
            "image": doc["images"][0] if doc["images"] else None,
        }])
        ctx.notes.update(updated=doc["updated"], title=doc["title"])
        return 1


COLLECTORS = [Air4ThaiSouth, AsmcSeasonalOutlook]
