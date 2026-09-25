"""Curated social accounts that share El Nino / impact information live.

Rule 1 of CLAUDE.md: no invented handles. Every entry below was resolved
against the live platform on `verified_at` and its returned display name
matched the expected owner (`name`). `scripts/verify_accounts.py` re-checks
all of them (existence + display name + last post) and must be re-run
before adding or changing an entry.

Candidates that were checked and rejected (2026-09-24):
- X @IRI_Columbia: 404 (the IRI account is @climatesociety, dormant: see below).
- X @NationThailand: exists but is an unrelated personal account (Nation
  Thailand is @Thenationth, kept).
- X Thai Meteorological Department: no official account found
  (@TMDThailand, @tmd_thailand, @TMD_Thailand, @ThaiMetDept all 404).
- X @DrLHeureux: unrelated person. Michelle L'Heureux / Emily Becker (NOAA
  ENSO blog): no account found on X or Bluesky under their names.
- X @EmilyBeckerClim, @ClimateReanalyzr, @climatereanalyzer: 404.
- Bluesky Climate Reanalyzer: no account found.
- Bluesky climate.noaa.gov (NOAA Climate.gov): exists, silent since 2025-06.
- Bluesky scottduncanwx.bsky.social: exists, silent since 2025-01.
- Bluesky thenasaearth.bsky.social: exists, 0 posts.
- Dormant on X at verification (last own post): @NOAAClimate (2025-06),
  @climatesociety / IRI (2024-02), @ECMWF (2025-03; ECMWF is active on
  Bluesky, kept there), @CoralReefWatch (reposts only, last 2026-06),
  @ThaiWeather (2022-10).
- Bluesky noaa.gov: handle conflict. The AppView shows it on NOAA's account
  but com.atproto.identity.resolveHandle returns another DID (displayed as
  "NOAA Fisheries"), so the handle cannot be trusted; nws.noaa.gov is kept.
- Telegram Thai PBS / Bangkok Post / Nation channels: exist but silent
  since 2021-2025. Samui Times: 1 post (2025).

`keep_all`: every post is stored (the account only posts on the topic).
Otherwise posts are filtered to ENSO / climate-impact topics.
"""

from __future__ import annotations

from typing import TypedDict


class Account(TypedDict, total=False):
    platform: str        # x | bluesky | telegram
    handle: str          # as used in the platform URL, without "@"
    name: str            # display name returned by the platform at verification
    why: str             # English: why this account matters here
    kind: str            # agency | scientist | media | local
    verified_at: str     # YYYY-MM-DD
    keep_all: bool


V = "2026-09-24"

ACCOUNTS: list[Account] = [
    # ---------------------------------------------------------------- X
    {"platform": "x", "handle": "NWSCPC", "name": "NWS Climate Prediction Center", "kind": "agency",
     "why": "Issues the official El Nino advisories (ENSO Advisory) and the monthly outlooks.",
     "verified_at": V, "keep_all": True},
    {"platform": "x", "handle": "NOAA", "name": "NOAA", "kind": "agency",
     "why": "US weather/ocean agency; ENSO announcements and extreme events.",
     "verified_at": V},
    {"platform": "x", "handle": "BOM_au", "name": "Bureau of Meteorology, Australia", "kind": "agency",
     "why": "Australian weather service; ENSO status and impacts in Asia-Pacific.",
     "verified_at": V},
    {"platform": "x", "handle": "WMO", "name": "World Meteorological Organization", "kind": "agency",
     "why": "WMO: global El Nino/La Nina updates and climate alerts.",
     "verified_at": V},
    {"platform": "x", "handle": "NASAEarth", "name": "NASA Earth", "kind": "agency",
     "why": "Satellite imagery of surface temperature anomalies and impacts.",
     "verified_at": V},
    {"platform": "x", "handle": "CopernicusECMWF", "name": "Copernicus ECMWF", "kind": "agency",
     "why": "European climate service C3S: monthly bulletins and seasonal forecasts.",
     "verified_at": V},
    {"platform": "x", "handle": "OCHAAsiaPac", "name": "UN OCHA Asia Pacific", "kind": "agency",
     "why": "UN humanitarian coordination in Asia-Pacific: droughts, floods, cyclones.",
     "verified_at": V},
    {"platform": "x", "handle": "hausfath", "name": "Zeke Hausfather", "kind": "scientist",
     "why": "Climate scientist (Berkeley Earth / Carbon Brief); El Nino and record analyses.",
     "verified_at": V},
    {"platform": "x", "handle": "BenNollWeather", "name": "Ben Noll", "kind": "scientist",
     "why": "Meteorologist (Washington Post), follows ENSO and its impacts in Asia closely.",
     "verified_at": V},
    {"platform": "x", "handle": "extremetemps", "name": "Extreme Temperatures Around The World",
     "kind": "scientist",
     "why": "Climatologist M. Herrera: live heat records, including in Thailand.",
     "verified_at": V},
    {"platform": "x", "handle": "ThaiPBSWorld", "name": "Thai PBS World", "kind": "media",
     "why": "Thai public broadcaster in English: weather, drought, floods.",
     "verified_at": V},
    {"platform": "x", "handle": "BangkokPostNews", "name": "Bangkok Post", "kind": "media",
     "why": "Thailand's newspaper of record; local impacts of El Nino.",
     "verified_at": V},
    {"platform": "x", "handle": "Thenationth", "name": "Thenationthailand", "kind": "media",
     "why": "Nation Thailand: TMD weather warnings relayed quickly.",
     "verified_at": V},
    {"platform": "x", "handle": "ThaigerNews", "name": "The Thaiger", "kind": "media",
     "why": "English-language Thai media; covers Koh Samui and daily weather warnings.",
     "verified_at": V},
    {"platform": "x", "handle": "KhaosodEnglish", "name": "Khaosod English", "kind": "media",
     "why": "English-language Thai media; floods, drought, pollution.",
     "verified_at": V},
    # ---------------------------------------------------------------- Bluesky
    {"platform": "bluesky", "handle": "nws.noaa.gov", "name": "National Weather Service",
     "kind": "agency", "why": "US weather service; CPC outlooks and El Nino.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "wmo-global.bsky.social",
     "name": "World Meteorological Organization", "kind": "agency",
     "why": "WMO: global El Nino/La Nina updates.", "verified_at": V},
    {"platform": "bluesky", "handle": "copernicusecmwf.bsky.social", "name": "Copernicus ECMWF",
     "kind": "agency", "why": "C3S: monthly climate bulletins and ocean temperatures.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "ecmwf.int", "name": "ECMWF", "kind": "agency",
     "why": "ENSO seasonal forecasts from the European centre.", "verified_at": V},
    {"platform": "bluesky", "handle": "copernicusmarine.bsky.social",
     "name": "The Copernicus Marine Service", "kind": "agency",
     "why": "State of the ocean: marine heatwaves, surface temperature.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "berkeleyearth.org", "name": "Berkeley Earth",
     "kind": "agency", "why": "Monthly global temperatures and the role of El Nino.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "zekehausfather.com", "name": "Zeke Hausfather",
     "kind": "scientist", "why": "El Nino analyses / global temperature records.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "andrewdessler.com", "name": "Andrew Dessler",
     "kind": "scientist", "why": "Climate scientist (Texas A&M); comments on ENSO and extremes.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "tdiliberto.bsky.social", "name": "Tom Di Liberto",
     "kind": "scientist", "why": "Former author of NOAA's ENSO blog; explains ENSO for a general audience.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "weatherwest.bsky.social", "name": "Daniel Swain",
     "kind": "scientist", "why": "Extremes specialist (drought, floods, fires).",
     "verified_at": V},
    {"platform": "bluesky", "handle": "climateofgavin.bsky.social", "name": "Gavin Schmidt",
     "kind": "scientist", "why": "Director of NASA GISS; tracks El Nino and global temperature.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "rarohde.bsky.social", "name": "Robert Rohde",
     "kind": "scientist", "why": "Berkeley Earth; ENSO charts and daily temperatures.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "leonsimons.com", "name": "Leon Simons", "kind": "scientist",
     "why": "Daily tracking of ocean temperatures and ENSO.", "verified_at": V},
    {"platform": "bluesky", "handle": "bennollweather.bsky.social", "name": "", "kind": "scientist",
     "why": "Ben Noll (Washington Post) on Bluesky; ENSO and impacts in Asia.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "katharinehayhoe.com", "name": "Katharine Hayhoe",
     "kind": "scientist", "why": "Climate scientist; shares the impacts of extremes.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "michaelemann.bsky.social", "name": "Michael E. Mann",
     "kind": "scientist", "why": "Climate scientist; comments on El Nino and warming.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "zacklabe.com", "name": "Zack Labe", "kind": "scientist",
     "why": "Climate Central; anomaly visualisations (ENSO, ice, SST).",
     "verified_at": V},
    {"platform": "bluesky", "handle": "extremetemps.bsky.social",
     "name": "Extreme Temperatures Around the World", "kind": "scientist",
     "why": "Live heat records, Southeast Asia included.", "verified_at": V},
    {"platform": "bluesky", "handle": "drjeffmasters.bsky.social", "name": "Dr. Jeff Masters",
     "kind": "scientist", "why": "Yale Climate Connections; cyclones and extremes.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "kristenbrown.bsky.social", "name": "Dr. Kristen Brown",
     "kind": "scientist", "why": "NOAA Coral Reef Watch scientist; coral bleaching.",
     "verified_at": V},
    {"platform": "bluesky", "handle": "oceanterra.org", "name": "Sam Burgess", "kind": "scientist",
     "why": "Deputy director of Copernicus C3S; climate bulletins.", "verified_at": V},
    {"platform": "bluesky", "handle": "carbonbrief.org", "name": "Carbon Brief", "kind": "media",
     "why": "Climate journalism; detailed El Nino analyses.", "verified_at": V},
    {"platform": "bluesky", "handle": "environment.theguardian.com",
     "name": "Guardian Environment", "kind": "media",
     "why": "The Guardian's environment section; global impacts.", "verified_at": V},
    {"platform": "bluesky", "handle": "mongabay.com", "name": "Mongabay", "kind": "media",
     "why": "Environment in Southeast Asia (fires, reefs, drought).", "verified_at": V},
    {"platform": "bluesky", "handle": "climateconnections.bsky.social",
     "name": "Yale Climate Connections", "kind": "media",
     "why": "Climate news and extreme weather.", "verified_at": V},
    # ---------------------------------------------------------------- Telegram
    {"platform": "telegram", "handle": "thethaiger", "name": "The Thaiger", "kind": "media",
     "why": "The Thaiger's Telegram channel (thethaiger.com links): weather and floods in Thailand.",
     "verified_at": V},
]


def accounts(platform: str) -> list[Account]:
    return [a for a in ACCOUNTS if a["platform"] == platform]
