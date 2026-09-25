"""How strongly El Nino / La Nina (ENSO) reaches each place: curated, with sources.

This is expert-assessed context, not a measurement, so every region carries its evidence
links (checked 2026-09-24: HTTP 200, or the DOI resolved through Crossref). A place outside
every region below is "not assessed": we do not guess a teleconnection.

Scale (`strength`, 0-4, higher = the place's weather depends more on ENSO):
  0 none known, 1 weak / indirect, 2 moderate, 3 strong, 4 very strong (core ENSO regions
  such as Indonesia, coastal Peru, eastern Australia; none of our places).
"""

from __future__ import annotations

SOURCES = {
    "noaa_impacts": {
        "title": "NOAA Climate.gov -- Global impacts of El Nino and La Nina (seasonal maps)",
        "url": "https://www.climate.gov/news-features/featured-images/"
               "global-impacts-el-ni%C3%B1o-and-la-ni%C3%B1a"},
    "juneng_tangang": {
        "title": "Juneng & Tangang (2005), Evolution of ENSO-related rainfall anomalies in "
                 "Southeast Asia region..., Climate Dynamics 25",
        "url": "https://doi.org/10.1007/s00382-005-0031-6"},
    "samui_rationing": {
        "title": "Bangkok Post, 29/07/2026 -- Koh Samui faces water rationing",
        "url": "https://www.bangkokpost.com/thailand/general/3293479/"
               "koh-samui-faces-water-rationing"},
    "bronnimann": {
        "title": "Bronnimann (2007), Impact of El Nino-Southern Oscillation on European "
                 "climate, Reviews of Geophysics 45",
        "url": "https://doi.org/10.1029/2006RG000199"},
    "metoffice": {
        "title": "Met Office -- El Nino and La Nina (effect on UK winters)",
        "url": "https://www.metoffice.gov.uk/weather/learn-about/weather/oceans/el-nino"},
    "wmo": {"title": "WMO -- El Nino/La Nina Updates",
            "url": "https://wmo.int/wmo-el-ninola-nina-updates"},
}

STRENGTH_LABELS = {0: "none known", 1: "weak / indirect", 2: "moderate", 3: "strong",
                   4: "very strong"}

# First matching box wins. Boxes: (lat_min, lat_max, lon_min, lon_max).
REGIONS = [
    {
        "id": "southeast_asia",
        "label": "Southeast Asia (Thailand, Malay peninsula, Maritime Continent)",
        "box": (-11.0, 25.0, 90.0, 155.0),
        "strength": 3,
        "mechanism": (
            "During El Nino the zone of rising, rain-making air over the warm Pacific moves "
            "east, away from Southeast Asia, so the region tends to get less rain and more "
            "heat. Studies of the region's rainfall find a dry anomaly that builds during the "
            "developing and mature phase of El Nino and moves across the region with the "
            "seasons (Juneng & Tangang 2005)."),
        "el_nino_effect": (
            "Drier and hotter than normal is the usual El Nino signal. On the Gulf side of "
            "southern Thailand (Koh Samui) most rain falls with the north-east monsoon, "
            "October to January; a weak monsoon leaves the island's small reservoirs low for "
            "the February-May dry season."),
        "outlook_2026_27": (
            "With a strong El Nino under way (NOAA), the risk to watch is a below-normal end "
            "of the 2026 monsoon followed by a long, hot 2027 dry season: water shortages "
            "(Samui already had PWA rotating supply from 3 August 2026) and heat. Check the "
            "ECMWF seasonal anomalies on this page and the Koh Samui watch for the numbers."),
        "sources": ["juneng_tangang", "noaa_impacts", "samui_rationing"],
    },
    {
        "id": "western_europe",
        "label": "Western Europe (France, British Isles, Benelux)",
        "box": (35.0, 72.0, -25.0, 30.0),
        "strength": 1,
        "mechanism": (
            "Europe is far from the tropical Pacific. The ENSO signal arrives through the "
            "jet stream and is small and season-dependent, mostly in late winter; the North "
            "Atlantic Oscillation (NAO) and the Atlantic dominate the year-to-year weather "
            "(Bronnimann 2007)."),
        "el_nino_effect": (
            "The Met Office notes that El Nino years are one factor that can raise the risk "
            "of colder winters in the UK; Normandy, across the Channel, shares much of that "
            "weather. The effect is a nudge in the odds, not a forecast."),
        "outlook_2026_27": (
            "A slightly higher chance of a colder or drier spell in late winter 2026-27 is "
            "possible but not reliable. The ECMWF seasonal anomalies on this page are a "
            "better guide than El Nino itself."),
        "sources": ["bronnimann", "metoffice", "noaa_impacts"],
    },
    {
        "id": "european_russia",
        "label": "Central European Russia (Moscow, Vladimir, Nizhny Novgorod)",
        "box": (45.0, 72.0, 30.0, 60.0),
        "strength": 1,
        "mechanism": (
            "Deep inside the continent, far from the Pacific: winter weather here is driven "
            "by the NAO / Arctic Oscillation and the Siberian High. The European ENSO studies "
            "find a weak, inconsistent signal that fades eastward (Bronnimann 2007). We found "
            "no agency statement specific to Vladimir Oblast."),
        "el_nino_effect": "No reliable El Nino signal documented for this region.",
        "outlook_2026_27": (
            "No ENSO-based expectation for winter 2026-27. Use the ECMWF seasonal anomalies "
            "on this page."),
        "sources": ["bronnimann", "noaa_impacts"],
    },
]


def assess(lat: float, lon: float) -> dict:
    """ENSO relevance for a point: the matching region with its evidence, or 'not assessed'."""
    for r in REGIONS:
        a, b, c, d = r["box"]
        if a <= lat <= b and c <= lon <= d:
            return {
                "assessed": True, "region": r["id"], "region_label": r["label"],
                "strength": r["strength"], "strength_label": STRENGTH_LABELS[r["strength"]],
                "mechanism": r["mechanism"], "el_nino_effect": r["el_nino_effect"],
                "outlook_2026_27": r["outlook_2026_27"],
                "sources": [SOURCES[s] for s in r["sources"]],
            }
    return {"assessed": False, "region": None, "region_label": None, "strength": None,
            "strength_label": "not assessed",
            "mechanism": ("No curated ENSO assessment covers this place yet. See the NOAA "
                          "impact maps for the broad picture."),
            "el_nino_effect": None, "outlook_2026_27": None,
            "sources": [SOURCES["noaa_impacts"], SOURCES["wmo"]]}
