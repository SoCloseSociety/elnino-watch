# Data sources

Every one of the 85 collectors below is registered in `backend/app/collectors/*.py`, `backend/app/local/*.py` or `backend/app/places/collectors.py` and shows up on the Sources page (`GET /api/sources`) with its state, last run, success rate and data freshness. "Every" is the polling interval, chosen to match how often the provider actually updates; "Max age" is how old the newest data may be before the source is flagged **stale**.

All of it is free and keyless unless the "Needs" column says otherwise. The data belongs to its providers and stays under their terms (see the licence notes at the end and the [README](../README.md#data-providers-and-licences)). This project only fetches, stores and displays it with its timestamp and a link back.

## ENSO and climate indices (17)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `cpc_oni` | Oceanic Nino Index (ONI) | [NOAA CPC](https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php) | 6 h | 90 d | none |
| `cpc_roni` | Relative Oceanic Nino Index (RONI) | [NOAA CPC](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/) | 6 h | 90 d | none |
| `cpc_weekly_sst` | Weekly Nino region SST (OISST) | [NOAA CPC](https://www.cpc.ncep.noaa.gov/data/indices/) | 6 h | 12 d | none |
| `cpc_soi` | Southern Oscillation Index (CPC, standardized) | [NOAA CPC](https://www.cpc.ncep.noaa.gov/data/indices/) | 6 h | 60 d | none |
| `psl_mei` | Multivariate ENSO Index (MEI.v2) | [NOAA PSL](https://psl.noaa.gov/enso/mei/) | 6 h | 80 d | none |
| `bom_soi` | Southern Oscillation Index (BoM, Troup) | [Australian Bureau of Meteorology](http://www.bom.gov.au/climate/enso/) | 6 h | 60 d | none |
| `cr_world_sst` | Daily world sea surface temperature (60S-60N) | [Climate Reanalyzer (Univ. of Maine) / NOAA OISST v2.1](https://climatereanalyzer.org/clim/sst_daily/) | 6 h | 4 d | none |
| `cr_nino34_daily` | Daily Nino 3.4 SST | [Climate Reanalyzer (Univ. of Maine) / NOAA OISST v2.1](https://climatereanalyzer.org/clim/sst_daily/) | 6 h | 4 d | none |
| `cpc_heat_content` | Equatorial Pacific upper-ocean heat content (0-300 m) | [NOAA CPC](https://www.cpc.ncep.noaa.gov/products/GODAS/) | 12 h | 60 d | none |
| `pmel_wwv` | Warm water volume + 0-300 m temperature (TAO/PMEL) | [NOAA PMEL (GTMBA / TAO)](https://www.pmel.noaa.gov/tao/wwv/index.html) | 12 h | 60 d | none |
| `jma_sst_indices` | Indian Ocean Dipole (DMI) + NINO.WEST (JMA) | [JMA Tokyo Climate Center](https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/iod_index.html) | 12 h | 60 d | none |
| `cpc_atmos_indices` | Trade winds, upper winds and dateline convection (CPC) | [NOAA CPC](https://www.cpc.ncep.noaa.gov/data/indices/) | 12 h | 60 d | none |
| `psl_mjo_romi` | Madden-Julian Oscillation (real-time OMI, NOAA PSL) | [NOAA PSL](https://psl.noaa.gov/mjo/) | 12 h | 12 d | none |
| `c3s_climate_pulse` | Copernicus Climate Pulse -- daily global air and sea temperature (ERA5) | [Copernicus Climate Change Service (C3S) / ECMWF](https://pulse.climate.copernicus.eu/) | 6 h | 5 d | none |
| `ncei_cag` | NOAA NCEI Climate at a Glance -- global and Asia monthly temperature anomaly | [NOAA National Centers for Environmental Information (NOAAGlobalTemp)](https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series) | 12 h | 60 d | none |
| `metoffice_hadobs` | UK Met Office HadCRUT5 and HadSST4 -- monthly global and tropical anomalies | [UK Met Office Hadley Centre (with UEA CRU for HadCRUT5)](https://www.metoffice.gov.uk/hadobs/) | 12 h | 75 d | none |
| `nasa_gistemp` | NASA GISTEMP v4 -- global temperature anomaly (monthly) | [NASA Goddard Institute for Space Studies (GISS)](https://data.giss.nasa.gov/gistemp/) | 12 h | 60 d | none |

## Official bulletins and outlooks (13)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `cpc_discussion` | CPC ENSO Diagnostic Discussion | [NOAA CPC](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml) | 3 h | 40 d | none |
| `iri_plume` | IRI ENSO forecast probabilities | [IRI / Columbia University (CCSR)](https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/) | 12 h | 40 d | none |
| `jma_outlook` | JMA El Nino Outlook | [Japan Meteorological Agency (Tokyo Climate Center)](https://ds.data.jma.go.jp/tcc/tcc/products/elnino/) | 6 h | 40 d | none |
| `climategov_enso_blog` | climate.gov ENSO blog | [NOAA climate.gov](https://www.climate.gov/news-features/department/enso-blog) | 1 h | 45 d | none |
| `wmo_enso` | WMO El Nino/La Nina Updates | [World Meteorological Organization](https://wmo.int/publication-series/el-ninola-nina-updates) | 6 h | 120 d | none |
| `tmd_warnings_en` | TMD -- weather warnings (English edition) | [Thai Meteorological Department](https://www.tmd.go.th/en/warning-and-events/warning-storm) | 1 h | 3 h | none |
| `asmc_haze_alerts` | ASMC -- transboundary haze alert level | [ASEAN Specialised Meteorological Centre (ASMC)](https://asmc.asean.org/asmc-alerts/) | 3 h | 9 h | none |
| `cpc_enso_probs` | CPC official ENSO probabilities + strength probabilities | [NOAA CPC](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/strengths/) | 6 h | 45 d | none |
| `ecmwf_nino_plume` | ECMWF SEAS5 Nino 3.4 forecast plume | [ECMWF (Copernicus C3S SEAS5)](https://charts.ecmwf.int/products/seasonal_system5_nino_plumes) | 12 h | 36 h | none |
| `ncei_monthly_report` | NOAA NCEI monthly global climate, drought and tropical cyclone reports | [NOAA National Centers for Environmental Information](https://www.ncei.noaa.gov/access/monitoring/monthly-report/) | 12 h | 40 d | none |
| `ecmwf_seas5_asia` | ECMWF SEAS5 -- 3-month rain and temperature outlook maps for Asia | [European Centre for Medium-Range Weather Forecasts (open charts, CC-BY-4.0)](https://charts.ecmwf.int/products/seasonal_system5_standard_rain) | 12 h | 40 d | none |
| `nasa_gmao_s2s` | NASA GMAO GEOS-S2S-3 -- El Nino and Indian Ocean forecast plumes | [NASA Global Modeling and Assimilation Office (GMAO)](https://gmao.gsfc.nasa.gov/gmao-products/geos-s2s-3/forecast-data_geos-s2s-3/plumes) | 12 h | 45 d | none |
| `asmc_seasonal_outlook` | ASMC -- ASEAN seasonal outlook (rain, temperature, haze) | [ASEAN Specialised Meteorological Centre (ASMC)](https://asmc.asean.org/asmc-seasonal-outlook/) | 12 h | 40 d | none |

## Ocean and sea state (4)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `tao_buoys` | TAO/TRITON buoys (equatorial Pacific) | [NOAA NDBC / PMEL (Global Tropical Moored Buoy Array)](https://tao.ndbc.noaa.gov/) | 3 h | 12 h | none |
| `crw_vs` | Coral Reef Watch -- heat stress (Gulf of Thailand) | [NOAA Coral Reef Watch (5 km Virtual Stations v3.1)](https://coralreefwatch.noaa.gov/product/vs/) | 12 h | 4 d | none |
| `openmeteo_marine` | Sea around Koh Samui (waves, swell, SST) | [Open-Meteo Marine (MeteoFrance MFWAM / ECMWF WAM, SST)](https://open-meteo.com/en/docs/marine-weather-api) | 1 h | 3 h | none |
| `noaa_sla_regions` | Satellite sea level anomaly -- Pacific, South China Sea, Gulf of Thailand, Samui | [NOAA NESDIS CoastWatch (blended multi-mission altimetry, ERDDAP)](https://coastwatch.noaa.gov/cw_html/SSH_SeaLevelAnomaly.html) | 12 h | 5 d | none |

## Hazards and disasters (8)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `gdacs` | GDACS -- current disaster alerts | [GDACS (EC Joint Research Centre / UN OCHA)](https://www.gdacs.org/) | 15 min | 1 h | none |
| `eonet` | NASA EONET -- open natural events | [NASA Earth Observatory Natural Event Tracker (EONET v3)](https://eonet.gsfc.nasa.gov/) | 15 min | 3 d | none |
| `thaiwater_dams_national` | Thailand -- large dam storage | [ThaiWater (HII) / Royal Irrigation Department](https://www.thaiwater.net/water/dam) | 6 h | 3 d | none |
| `jma_typhoons` | JMA RSMC Tokyo -- West Pacific tropical cyclones (track + 5-day forecast) | [Japan Meteorological Agency (RSMC Tokyo)](https://www.jma.go.jp/bosai/map.html#contents=typhoon&lang=en) | 30 min | 3 h | none |
| `jtwc_warnings` | JTWC -- tropical cyclone warnings (NW Pacific, North Indian Ocean) | [US Joint Typhoon Warning Center](https://www.metoc.navy.mil/jtwc/jtwc.html) | 30 min | 3 h | none |
| `usgs_quakes_region` | USGS -- M4.5+ earthquakes within 3000 km (past 7 days) | [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/earthquakes/map/) | 30 min | 3 h | none |
| `ptwc_tsunami` | NOAA PTWC -- latest tsunami message (Pacific) | [NOAA Pacific Tsunami Warning Center](https://www.tsunami.gov/) | 15 min | 2 h | none |
| `reliefweb_reports` | ReliefWeb -- humanitarian reports on El Nino and Thailand | [UN OCHA ReliefWeb](https://reliefweb.int/) | 3 h | 7 d | `RELIEFWEB_APPNAME` |

## Satellite products (5)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `firms_fires` | NASA FIRMS -- active fires (VIIRS, 24 h) | [NASA FIRMS (LANCE, VIIRS S-NPP 375 m)](https://firms.modaps.eosdis.nasa.gov/) | 3 h | 18 h | none |
| `asmc_hotspots` | ASMC -- VIIRS hotspots by country/region | [ASEAN Specialised Meteorological Centre (ASMC)](https://asmc.asean.org/asmc-haze-hotspot-daily-new/) | 6 h | 3 d | none |
| `nasa_worldview_snapshots` | NASA Worldview snapshots -- Samui, Gulf of Thailand, SE Asia haze, Pacific SST | [NASA Worldview Snapshots (GIBS imagery)](https://worldview.earthdata.nasa.gov/) | 6 h | 2 d | none |
| `nasa_cmr_latency` | NASA Earthdata CMR -- how fresh key satellite datasets are | [NASA Earthdata Common Metadata Repository (CMR)](https://cmr.earthdata.nasa.gov/search/) | 3 h | 12 h | none |
| `nasa_grace_drought` | NASA GRACE-FO drought indicators -- Asia maps (weekly) | [NASA GSFC / University of Nebraska-Lincoln NDMC (GRACE-FO data assimilation)](https://nasagrace.unl.edu/) | 12 h | 16 d | none |

## News (7)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `gdelt_news` | GDELT -- El Nino & impacts news (multi-language) | [GDELT Project DOC 2.0 API](https://www.gdeltproject.org/) | 20 min | 2 d | none |
| `google_news` | Google News -- El Nino in 8 languages + Thailand / Koh Samui | [Google News RSS](https://news.google.com/) | 20 min | 2 d | none |
| `news_science_rss` | Agency & climate-science RSS (NOAA, NASA, Copernicus, Carbon Brief, ...) | [Publisher RSS feeds](https://www.carbonbrief.org/) | 30 min | 7 d | none |
| `news_thailand_rss` | Thai & regional press RSS (Thaiger Koh Samui, Bangkok Post, Thairath, ...) | [Publisher RSS feeds](https://thethaiger.com/tag/koh-samui) | 15 min | 2 d | none |
| `nasa_eo_iotd` | NASA Earth Observatory -- Image of the Day (ENSO and impact stories) | [NASA Earth Observatory](https://earthobservatory.nasa.gov/topic/image-of-the-day) | 6 h | 18 h | none |
| `youtube_channels` | YouTube -- NOAA, NASA, WMO, Copernicus, Thai PBS, The Weather Channel | [YouTube channel RSS (keyless)](https://www.youtube.com/@NOAA) | 1 h | 14 d | none |
| `newsletters_rss` | Climate newsletters (The Climate Brink, Yale Climate Connections, Climate Signals) | [Publisher RSS feeds](https://www.theclimatebrink.com/) | 2 h | 45 d | none |

## Social media (6)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `bluesky_accounts` | Bluesky -- verified ENSO scientists, agencies and media | [Bluesky public AppView](https://bsky.app/) | 15 min | 1 d | none |
| `bluesky_search` | Bluesky -- live search (El Nino, ENSO, Koh Samui) | [Bluesky (authenticated app password)](https://bsky.app/search) | 15 min | 1 d | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` |
| `mastodon_tags` | Mastodon -- #ElNino #ENSO #KohSamui hashtag timelines | [Mastodon public API](https://mastodon.social/tags/ElNino) | 15 min | 1 d | none |
| `reddit_search` | Reddit -- r/weather r/climate (El Nino) + r/Thailand r/kohsamui (impacts) | [Reddit search RSS](https://www.reddit.com/r/kohsamui/) | 10 min | 1 d | none |
| `x_posts` | X (Twitter) -- verified accounts + El Nino / Koh Samui search | [X API v2 / cookie session / keyless (FxTwitter, syndication, nitter)](https://x.com/NWSCPC) | 15 min | 1 d | none |
| `telegram_channels` | Telegram -- public channels (web preview) | [Telegram t.me/s preview](https://t.me/s/thethaiger) | 15 min | 3 d | none |

## Koh Samui (local watch) (14)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `nasa_power_samui` | NASA POWER -- Koh Samui daily weather, sunshine and 2001-2020 normals | [NASA Langley POWER (MERRA-2, GEOS-IT, CERES FLASHFlux)](https://power.larc.nasa.gov/) | 12 h | 6 d | none |
| `air4thai_south` | Air4Thai -- measured PM2.5 / AQI, southern Thailand stations | [Pollution Control Department (PCD), Thailand](https://air4thai.pcd.go.th/webV3/) | 1 h | 6 h | none |
| `webcams_images` | Webcams: buoy and satellite still images | [NOAA NDBC / JMA MSC / NOAA NESDIS STAR](https://www.ndbc.noaa.gov/buoycams.php) | 30 min | 2 h | none |
| `webcams_streams` | Webcams: Koh Samui, ferry route, Thailand and ENSO-region streams | [YouTube (venue channels) / SkylineWebcams / owner pages](https://www.skylinewebcams.com/en/webcam/thailand/surat-thani/ko-samui.html) | 1 h | 3 h | none |
| `webcams_windy` | Webcams: Windy Webcams API (Samui, ferry route) | [Windy.com Webcams API v3](https://api.windy.com/webcams) | 1 h | 3 h | `WINDY_WEBCAMS_KEY` |
| `openmeteo_samui` | Koh Samui -- 16-day forecast + past 92 days | [Open-Meteo (DWD ICON, ECMWF IFS, NOAA GFS... best match)](https://open-meteo.com/en/docs) | 3 h | 9 h | none |
| `openmeteo_samui_era5` | Koh Samui -- ERA5 observed (200 d) + 1991-2020 normals | [Open-Meteo archive (ECMWF ERA5)](https://open-meteo.com/en/docs/historical-weather-api) | 12 h | 10 d | none |
| `openmeteo_samui_air` | Koh Samui -- air quality (PM2.5, PM10, AQI) | [Open-Meteo air quality (Copernicus CAMS)](https://open-meteo.com/en/docs/air-quality-api) | 3 h | 9 h | none |
| `openmeteo_samui_seasonal` | Koh Samui -- seasonal forecast (6 months) | [Open-Meteo seasonal (ECMWF SEAS5)](https://open-meteo.com/en/docs/seasonal-forecast-api) | 1 d | 3 d | none |
| `thaiwater_samui_rain` | Koh Samui -- rain gauges (observed 24 h rain) | [ThaiWater / HII (Hydro-Informatics Institute), stations HII + TMD](https://www.thaiwater.net/) | 1 h | 6 h | none |
| `thaiwater_dams` | Surat Thani -- Ratchaprapa dam (storage) | [ThaiWater / Royal Irrigation Department](https://www.thaiwater.net/) | 6 h | 4 d | none |
| `tmd_warnings` | TMD -- weather warnings (heavy rain, waves, storms) | [Thai Meteorological Department](https://www.tmd.go.th/) | 1 h | 6 h | none |
| `pwa_samui_notices` | Koh Samui -- PWA water-supply interruption notices | [PWA (Provincial Waterworks Authority), Ko Samui branch](https://www.pwa.co.th/news/call1662) | 3 h | 9 h | none |
| `samui_era5_history` | Koh Samui -- ERA5 monthly history since 1950 (El Nino analogs) | [Open-Meteo archive (ECMWF ERA5)](https://open-meteo.com/en/docs/historical-weather-api) | 1 h | 3 d | none |

## Places comparison (11)

| Collector | What | Provider | Every | Max age | Needs |
|---|---|---|---|---|---|
| `places_forecast` | Places -- current conditions + 16-day forecast | [Open-Meteo (best-match weather models)](https://open-meteo.com/en/docs) | 3 h | 9 h | none |
| `places_climate` | Places -- 1991-2020 climate normals + last 400 days (ERA5) | [Open-Meteo archive (ECMWF ERA5)](https://open-meteo.com/en/docs/historical-weather-api) | 1 h | 3 d | none |
| `places_air` | Places -- air quality and pollen (CAMS) | [Open-Meteo air quality (Copernicus CAMS)](https://open-meteo.com/en/docs/air-quality-api) | 3 h | 9 h | none |
| `places_marine` | Places -- sea state near the coast (waves, sea temperature) | [Open-Meteo Marine (MeteoFrance MFWAM / ECMWF WAM, SST)](https://open-meteo.com/en/docs/marine-weather-api) | 3 h | 9 h | none |
| `places_seasonal` | Places -- seasonal outlook (ECMWF SEAS5, 6 months) | [Open-Meteo seasonal (ECMWF SEAS5)](https://open-meteo.com/en/docs/seasonal-forecast-api) | 1 d | 3 d | none |
| `places_projection` | Places -- climate projections to 2050 (CMIP6) | [Open-Meteo climate API (CMIP6 HighResMIP)](https://open-meteo.com/en/docs/climate-api) | 2 h | 6 h | none |
| `places_flood` | Places -- river discharge of the nearest river (GloFAS) | [Open-Meteo flood API (Copernicus GloFAS v4)](https://open-meteo.com/en/docs/flood-api) | 6 h | 18 h | none |
| `places_quakes` | Places -- earthquakes within 300 km (USGS) | [USGS Earthquake Hazards Program (FDSN event service)](https://earthquake.usgs.gov/earthquakes/search/) | 1 h | 3 h | none |
| `places_fires` | Places -- active fires within 100 km (NASA FIRMS, 24 h) | [NASA FIRMS (LANCE, VIIRS S-NPP 375 m)](https://firms.modaps.eosdis.nasa.gov/) | 6 h | 18 h | none |
| `places_warnings` | Places -- official weather warnings (Meteoalarm / Meteo-France, Roshydromet) | [Meteoalarm (EUMETNET; Meteo-France vigilance) + Hydrometcenter of Russia](https://meteoalarm.org/) | 1 h | 3 h | none |
| `places_advisories` | Places -- official travel advice (FCDO, US State, France Diplomatie) | [UK FCDO (GOV.UK), US Department of State, France Diplomatie](https://www.gov.uk/foreign-travel-advice) | 12 h | 36 h | none |

## Licence and terms notes (per provider family)

These notes summarise each provider's published terms as understood on 2026-09-25. They are not legal advice: check the provider's page before reusing any data downstream.

| Provider family | Terms (summary) |
|---|---|
| NOAA (CPC, PSL, NDBC / PMEL, Coral Reef Watch, NESDIS CoastWatch, NCEI, PTWC, climate.gov) | US Government work, public domain; cite NOAA and the product. |
| NASA (EONET, FIRMS, GIBS / Worldview, POWER, GISTEMP, CMR, GMAO, Earth Observatory) | Public domain / no restrictions; FIRMS and GIBS ask for attribution ("NASA FIRMS", "NASA GIBS"). |
| USGS Earthquake Hazards Program | Public domain (US Government work). |
| Open-Meteo (forecast, marine, air quality, archive ERA5, seasonal, climate, flood, geocoding) | CC BY 4.0, non-commercial free tier (10,000 calls / day per IP); attribution required. Upstream models: DWD, ECMWF, NOAA, Meteo-France, Copernicus. |
| Copernicus / ECMWF (Climate Pulse, open charts, SEAS5, CAMS via Open-Meteo, GloFAS via Open-Meteo) | Copernicus licence (free, attribution); ECMWF open charts CC BY 4.0. |
| Australian Bureau of Meteorology | CC BY 3.0 AU for most climate products; check the page. |
| Japan Meteorological Agency (Tokyo Climate Center, RSMC Tokyo) | JMA site terms (Government of Japan Standard Terms of Use, CC BY 4.0 compatible). |
| IRI / Columbia University | IRI terms of use; forecast probabilities cited with issue date. |
| World Meteorological Organization | WMO publication terms; the app stores titles, dates and links. |
| UK Met Office Hadley Centre (HadCRUT5, HadSST4) | Open Government Licence v3 (with UEA CRU for HadCRUT5). |
| Climate Reanalyzer (University of Maine) | Free for non-commercial use with attribution; underlying data NOAA OISST v2.1. |
| GDACS (EC JRC / UN OCHA) | Free to use with attribution to GDACS. |
| UN OCHA ReliefWeb | ReliefWeb API terms (app name required); content belongs to its publishers. |
| ASEAN Specialised Meteorological Centre | ASMC site terms; values quoted with their date and a link. |
| Thai government sources (TMD, PWA, ThaiWater / HII, Royal Irrigation Department, Air4Thai / PCD) | Each agency's site terms; public bulletins and measurements, linked back to the source page. |
| US Joint Typhoon Warning Center | US Government work, public domain. |
| Meteoalarm (EUMETNET), Hydrometcenter of Russia, UK FCDO, US Department of State, France Diplomatie | Official public warnings and travel advice; FCDO under OGL v3, US State public domain, France Diplomatie under Licence Ouverte (Etalab). |
| GDELT Project | Open; cite "GDELT Project". Rate limit 1 request / 5 s respected. |
| Google News RSS, publisher RSS feeds, YouTube channel RSS, newsletters | Only titles, dates and links are stored (never full text); each item links to the publisher. Follow each publisher's terms. |
| Bluesky, Mastodon, Reddit, X, Telegram (public posts only) | Public posts read through public / documented endpoints and linked back; platform terms apply. Curated accounts were verified against the live platform. |
| Webcams (NOAA BuoyCAMs, JMA MSC, NESDIS STAR, YouTube venue channels, SkylineWebcams, Windy Webcams API) | Only feeds their owner publishes for public viewing; where reuse of frames is not allowed the app links to the official page (`mode: link`). Windy needs an API key. |
| OpenStreetMap (Nominatim geocoding), Esri / HERE / Garmin (basemap tiles) | ODbL (OSM) and the basemap provider's terms; attribution is shown on the map. |
| RainViewer (rain radar tiles) | Free tier of the RainViewer API, attribution shown on the map. |

