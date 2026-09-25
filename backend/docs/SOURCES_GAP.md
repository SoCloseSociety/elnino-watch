# Source gap analysis (2026-09-24)

Scope of this file: ENSO ocean/atmosphere indices, hazards, Thailand/Samui and media
(modules `extra_ocean`, `extra_atmos`, `extra_hazards`, `extra_thailand`, `extra_media`).
NASA / space-agency / met-agency deep sources (Earthdata, PO.DAAC, GISTEMP, POWER,
Worldview, GIBS, GRACE, GMAO, JAXA, ESA/Copernicus bulletins, Met Office, NCEI, Berkeley
Earth) belong to `extra_nasa` / `extra_agencies` and are not evaluated here.

Every verdict below comes from a live request made on 2026-09-24 from the workstation
(UA `ElNinoWatch/0.1`), unless marked otherwise. "added" = implemented, tested against a real
captured payload (tests/fixtures/extra/) and run live once through `run_collector`.

## Added (16 collectors)

| Collector | Module | Source / URL | Stores | Live run 2026-09-24 |
|---|---|---|---|---|
| `cpc_enso_probs` | extra_ocean | CPC official ENSO probabilities + strength probabilities, `.../enso/roni/probabilities/` + `.../roni/strengths/` (HTML tables) | status `cpc_enso_probs` | ok, 18 rows; issued 2026-09; SON: 97% very strong El Nino (>= +2.0 C), ASO 77% |
| `cpc_heat_content` | extra_ocean | CPC `ocean/index/heat_content_index.txt` | `heat_content_{130e_80w,160e_80w,180w_100w}_anom` | ok, 1716 rows; 2026-08 180W-100W +3.23 C |
| `pmel_wwv` | extra_ocean | PMEL `tao/wwv/data/{wwv,wwv_west,wwv_east,t300,t300_west,t300_east}.dat` | `wwv_anom`, `wwv_west_anom`, `wwv_east_anom`, `wwv_total` (1e14 m3), `t300_anom`, `t300_west_anom`, `t300_east_anom`, `t300_total` (degC) | ok, 4480 rows; 2026-08 wwv_anom +3.46, east +4.01, west -0.56 |
| `jma_sst_indices` | extra_ocean | JMA TCC `elnino/index/sstindex/base_period_9120/{DMI,WIN,EIN,Nino_West,Nino_3}/anomaly` | `dmi_jma_anom`, `iod_west_jma_anom`, `iod_east_jma_anom`, `nino_west_jma_anom`, `nino3_jma_anom` | ok, 2800 rows; 2026-08 DMI +0.37, NINO.3 +3.5, NINO.WEST +0.1 |
| `ecmwf_nino_plume` | extra_ocean | ECMWF opencharts API `seasonal_system5_nino_plumes` (axis + product, NINO3-4 and NINO3-4_rel) | status `ecmwf_nino_plume` {issued, label, images} | ok; issued 2026-09-01 |
| `cpc_atmos_indices` | extra_atmos | CPC `data/indices/{wpac850,cpac850,epac850,zwnd200,olr}` (ANOMALY block, standardized in meta) | `trade_wind_850_{wpac,cpac,epac}_anom`, `zonal_wind_200_anom` (m/s), `olr_dateline_anom` (W/m2) | ok, 2854 rows; 2026-08 cpac -6.3 m/s (std -2.5), OLR -14.9 |
| `psl_mjo_romi` | extra_atmos | NOAA PSL `mjo/mjoindex/romi.cpcolr.1x.txt` | `mjo_romi_amplitude`, `mjo_romi_pc1`, `mjo_romi_pc2` (last 2 years, daily) | ok, 2178 rows; 2026-09-19 amplitude 1.10 |
| `jma_typhoons` | extra_hazards | JMA bosai `typhoon/data/targetTc.json` + `TCxxxx/{forecast,specifications}.json` | events `cyclone` (LineString track + forecast, distance to home) | ok, 1 storm: TS Surigae (2626), closest 3189 km, green |
| `jtwc_warnings` | extra_hazards | JTWC `rss/jtwc.rss` + `products/<code>web.txt` + `abpwweb.txt` | events `cyclone` (WP + IO basins) + official feed (advisory) | ok, 3 items: wp2526, io0126 (final), abpw advisory |
| `usgs_quakes_region` | extra_hazards | USGS `summary/4.5_week.geojson`, filtered to 3000 km | events `earthquake` | ok, 13 of 102 worldwide |
| `ptwc_tsunami` | extra_hazards | NOAA PTWC `events/xml/PHEBAtom.xml` | official feed | ok, 1 (information statement, Puerto Rico) |
| `reliefweb_reports` | extra_hazards | ReliefWeb API v2 `reports` | official feed | needs_config: `RELIEFWEB_APPNAME` (API answers 403 "not using an approved appname" for `elnino-watch`) |
| `air4thai_south` | extra_thailand | PCD Air4Thai `services/getNewAQI_JSON.php` (173 stations), stations within 300 km | `air4thai_<id>_{pm25,pm10,aqi}` + status `air4thai_samui` | ok, 18 rows / 8 stations; nearest Surat Thani (42t, 87 km) PM2.5 7.0 |
| `asmc_seasonal_outlook` | extra_thailand | ASMC `asmc-seasonal-outlook/` (HTML) | status `asmc_seasonal_outlook` + official feed | ok; "Seasonal Forecast for September- November 2026", updated 2026-09-02 |
| `youtube_channels` | extra_media | YouTube channel RSS (6 channels, ids verified live, feed title checked every run) | news feed, tag `video` | ok, 4 items (WMO 1, Thai PBS 2, The Weather Channel 1) |
| `newsletters_rss` | extra_media | The Climate Brink, Yale Climate Connections, Climate Signals RSS | research/news feed, tag `newsletter` | ok, 7 items (Climate Brink 7/20) |

Notes:
- Air4Thai serves a Let's Encrypt leaf (issuer YR1) with an unrelated Sectigo chain; Python/
  OpenSSL + certifi cannot verify it (`CERTIFICATE_VERIFY_FAILED`). The collector adds the two
  missing PUBLIC Let's Encrypt intermediates (YR1 and "Root YR" cross-signed by ISRG Root X1,
  fetched from the leaf's AIA URLs) to a certifi context. Verification stays on (checked:
  expired.badssl.com is still rejected).
- YouTube channel ids scraped from the @handle pages were NOT trusted as-is: the first id found
  on the `@WMO` page belonged to "Wilson Mora" and on the `@NASA` page to "Learn With NASA".
  Only ids whose own feed `<title>` matched the agency were kept (and the title is re-checked on
  every run).

## Evaluated and not added

| Candidate | URL tried | Verdict | Evidence |
|---|---|---|---|
| BoM RMM MJO index | bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt | blocked | 403 "Your access is blocked due to the detection of a potential automated access request" (any UA). Replaced by PSL ROMI. |
| BoM IOD / weekly indices | ftp.bom.gov.au/anon/home/ncc/www/sco/ | not available | anonymous FTP only has `soi`, `ahead`, `grids`; web pages blocked as above |
| CPC NMME Nino3.4 text | cpc.ncep.noaa.gov/products/NMME/current/nino34.rescaling.ENSMEAN.txt | dead | 404; the NMME plume page only serves PNG images (images/nino34.rescaling.*.png) |
| CPC MJO OLR pentad index | cpc.ncep.noaa.gov/products/precip/CWlink/daily_mjo_index/proj_norm_order.ascii | superseded | 200 but last filled pentad 2026-08-26 (1 month lag); ROMI (daily, 5 d lag) added instead |
| CPC ERSSTv5 monthly Nino | cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii | redundant | 200, last row 2026-06; ONI/RONI + weekly OISST already cover it |
| PSL DMI (HadISST) | psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data | too late | 200, last value 2026-05 (4 month lag); JMA DMI (1 month lag) added instead |
| JAMSTEC weekly DMI | jamstec.go.jp/aplinfo/sintexf/DATA/dmi.weekly.txt | moved | 200 but body: "Please visit our new website APL VirtualEarth" (JS app, no file) |
| OSMC DMI | stateoftheocean.osmc.noaa.gov/sur/data/dmi.nc | not added | 200 netCDF; no netCDF reader in the stack, JMA DMI covers the need |
| APCC ENSO outlook | apcc21.org/ser/enso.do?lang=en | not machine-readable | 200 but content rendered by JavaScript (no outlook text in HTML) |
| KMA ENSO page | weather.go.kr/w/eng/climate/enso.do | not added | 200, no structured data; national, redundant with CPC/IRI/JMA/BoM/ECMWF |
| NIWA seasonal outlook | niwa.co.nz/.../seasonal-climate-outlook | irrelevant | New Zealand outlook |
| Copernicus C3S seasonal Nino3.4 (CDS) | cds.climate.copernicus.eu | needs key `CDSAPI_KEY`, not implemented | GRIB/netCDF via queued CDS requests; ECMWF SEAS5 plume (keyless chart) added instead |
| NOAA OISST daily anomaly map | ospo.noaa.gov/data/sst/anomaly/2026/ct5km_ssta_v3.1_global_20260923.png; CRW coraltemp ssta png | dead URL pattern | 404 for both; imagery belongs to extra_nasa / layers |
| CHIRPS rainfall | data.chc.ucsb.edu/products/CHIRPS-2.0/ | not added | 200, GeoTIFF/netCDF grids only; no raster library in the stack |
| SPEI global drought monitor | spei.csic.es/map/maps.html | not added | 200, map app; data as netCDF |
| Copernicus Global Drought Observatory | drought.emergency.copernicus.eu/api/wms | down | 502 on GetCapabilities |
| GloFAS | globalfloods.eu | needs account | 200 landing page; data via EWDS/CDS with key |
| FEWS NET | fdw.fews.net/api/ipcphase/?country_code=TH | irrelevant | 200 but `[]`: no Thailand coverage |
| WFP HungerMap | api.hungermapdata.org/v2/adm0/THA/countryData.json | down / no Thailand | 503; `v2/info/country` 200 (list only) |
| ReliefWeb | api.reliefweb.int/v2/reports?appname=elnino-watch | needs approved appname | 403 "You are not using an approved appname" -> implemented as `reliefweb_reports` (needs_config) |
| PAGASA (Philippines) | pagasa.dost.gov.ph | not added | 200 HTML only; West Pacific storms already covered by JMA + JTWC + GDACS |
| NCHMF (Vietnam) | nchmf.gov.vn/kttv/en-US/1/index.html | not added | 200 HTML only, no feed/API found; storms covered by JMA/JTWC |
| TMD monthly / seasonal forecast | tmd.go.th/en/climate/monthly-forecast, /seasonal-forecast | not machine-readable | 200 but content rendered by JavaScript (only navigation in HTML) |
| TMD data API | data.tmd.go.th/api/WeatherForecast7Days/V2/?uid=..&ukey=.. | needs registration (`TMD_UID`, `TMD_UKEY`), not implemented | 200 with a shared demo uid/ukey pair; a registered key should be used, so not implemented; Open-Meteo already gives the Samui forecast |
| Royal Irrigation Dept reservoirs | app.rid.go.th/reservoir/api/dam/public/<date> | redundant | 200 JSON (35 large dams) but `thaiwater_dams_national` already stores them; `rsvmiddle` endpoint returns PHP errors |
| GISTDA disaster API (flood, hotspots, drought) | api-gateway.gistda.or.th/api/2.0/resources/features/{flood,viirs,drought}/... | needs key `GISTDA_API_KEY`, not implemented | 407 {"detail":"Authentication Required"}; payload format could not be captured without a key (rule 7) |
| DDC dengue weekly counts | ddcopendata.ddc.moph.go.th (datasets 461, 658, 687) | not a live source | static uploaded xlsx/csv files, last update 2026-08; no weekly API |
| DDPM (Dept. of Disaster Prevention) | disaster.go.th | not added | 200 HTML portal, no feed found; `/th/index` 404 |
| PEA outage announcements | eservice.pea.co.th/PowerOutage/ | not added | 200 HTML form application, no keyless feed found |
| Samui airport (USM) flight status | (Bangkok Airways / aggregators) | not added | no keyless, licensed flight-status API; exit routes already link the operators |
| The Eyewall newsletter | theeyewall.com/feed/ | blocked | 403 |
| Michael Lowry / Ben Noll Substack | michaellowry.substack.com/feed, bennoll.substack.com/feed | not a feed | 200 but returns the Substack profile HTML, not RSS |
| Thai PBS World RSS | thaipbsworld.com/feed/ | dead | 200 "Page Not Found" |
| Nation Thailand RSS | nationthailand.com/rss | dead | 200 HTML page, not RSS |
| NOAA Climate YouTube | channel UCAoqY69CgTdx-xT55DwtiXg | inactive | last video 2025-04-03 |
| Met Office / Climate Central / Severe Weather Europe YouTube | UCylCbuzRsB92Gc1l8ru6VIg, UCsjQVs2e8swdVXQWGP6uFPg, UCyI3oFI4GvdfAPdflNqxPBQ | inactive | last videos 2024-09, 2017-08, 2022-02 |
| Climate One podcast | feeds.simplecast.com/climateone | dead | 404 |

## ScanGithub findings

- Local library search (`POST /api/repos/search`, no GitHub quota) on topics el-nino / enso /
  oceanic-nino-index / sea-surface-temperature / coral-reef-watch / tropical-cyclones /
  indian-ocean-dipole / madden-julian-oscillation: 38 repos, most noise (enso-org, laravel-enso).
  Relevant: `gabrielmpp/climate_indices`, `ahuang11/ninodata`, `andyg2/el-nino-vis`,
  `DogInfantry/El_Nino`, `wbp318/el-nino-26`, `ferariz/enso-forecast`, `senclimate/XRO`,
  `salvaRC/Graphino`, `Dubey411/Earth2100`.
- Data sources harvested from their code (raw files, no search quota):
  - `ahuang11/ninodata`: CPC `data/indices/{wpac850,cpac850,epac850,olr,sstoi.indices}`, PMEL
    `tao/wwv/data/{wwv,wwv_west,wwv_east,t300,t300_west,t300_east}.dat` -> all added.
  - `andyg2/el-nino-vis`: ERDDAP `coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg.json`,
    `tabledap/pmelTaoMonT.json`, CPC `ersst5.nino.mth.91-20.ascii` -> ERSST redundant; ERDDAP
    gridded OISST not needed (Climate Reanalyzer daily Nino 3.4 already stored).
  - `DogInfantry/El_Nino`: PSL ERSSTv5 netCDF, `psl.noaa.gov/data/climateindices/list/`, EM-DAT,
    World Bank commodity prices -> out of scope (no live hazard or ENSO value).
  - `gabrielmpp/climate_indices`: PSL correlation indices, CPC `data/indices/req` -> covered.
- An explicit-topic scan (#85, "elnino-watch source gap") was submitted with a hand-written plan;
  the service re-expanded the need text anyway (dataset / leak vocabulary, 76 queries) and it
  was cancelled after 41 queries / 226 API calls. Lesson: this ScanGithub build ignores a
  submitted `plan.topics` for new scans; use the local library search instead.
