# NASA and other agencies: source evaluation (2026-09-24)

Owner: the extra_nasa / extra_agencies agent. Modules: `app/collectors/extra_nasa.py`,
`app/collectors/extra_agencies.py`, `app/layers_extra.py` (EXTRA_LAYERS). Everything listed
as **added** was fetched live on 2026-09-24 with the app's User-Agent and runs through
`run_collector`; tests use real captured payloads under `tests/fixtures/extra_nasa/`.
ENSO indices, hazards, Thailand and media sources are evaluated in `SOURCES_GAP.md` (other
agent) and are not repeated here.

Verdicts: **added** / **needs key** / **blocked** / **irrelevant** (duplicate or no value
for this app) / **dead** (gone, or no longer updated).

## NASA

| Candidate | URL | Verdict | Evidence |
|---|---|---|---|
| NASA POWER daily point (Samui) | power.larc.nasa.gov/api/temporal/daily/point | added (`nasa_power_samui`) | 200 JSON; T2M 2026-09-21 = 28.56 degC, rain 4.44 mm; 2026-09-22..24 = -999 (fill, skipped); solar last 2026-09-19 |
| NASA POWER climatology | power.larc.nasa.gov/api/temporal/climatology/point | added (same collector, status `samui_power`) | 200 JSON; 2001-2020; SEP T2M 27.90, NOV rain 12.5 mm/day |
| POWER vs Open-Meteo ERA5 cross-check | (DB) | added (status `samui_power_crosscheck`) | 55 common days: Tmax POWER-ERA5 +0.60 degC (MAE 0.77), rain 290 vs 189 mm |
| GISTEMP v4 global monthly | data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv | added (`nasa_gistemp`) | 200 CSV; Aug 2026 = +1.40 degC (1951-1980) |
| GISTEMP zonal | .../ZonAnn.Ts+dSST.csv | added (annual 24S-24N only) | 200; 2025 tropics = +0.86. Monthly zonal CSV not published |
| Worldview Snapshots API | wvs.earthdata.nasa.gov/api/v1/snapshot | added (`nasa_worldview_snapshots`, status `snapshots`) | 200 image/jpeg, 5 views for 2026-09-23 verified (12-257 kB). A bbox crossing the date line returns 500, a no-data day returns a 1.2 kB black JPEG (rejected by size) |
| Earthdata CMR granule search | cmr.earthdata.nasa.gov/search/granules.json | added (`nasa_cmr_latency`, status `nasa_dataset_latency`) | 200 JSON; lags: MUR 17 h, OISST 38 h, IMERG 30-min 5 h, IMERG Early daily 14 h, Late 38 h, SMAP L4 62 h, SMAP L3 14 h, Sentinel-6 NRT 2.5 h, GRACE-FO (Jul 2026) 55 d, GRACE-DA (week of 2026-06-29) 81 d, NASA-SSH grid (2026-05-16) 131 d |
| GRACE-FO drought indicators (NDMC/UNL) | nasagrace.unl.edu/globaldata/ | added (`nasa_grace_drought`, status `grace_drought_asia`) | 200 dir listing; latest 20260921 (posted 2026-09-22); GRACE_{GWS,RTZSM,SFSM}_AS_20260921.png 200. Thailand/Indochina mostly <= 5th percentile |
| GMAO GEOS-S2S-3 plumes | gmao.gsfc.nasa.gov/lookup_images/?...type=plumes | added (`nasa_gmao_s2s`, status `gmao_s2s_plume`) | 200 JSON -> nino3.4_sep2026_plume_S2S.png (Last-Modified 2026-09-02); ensemble mean Nino 3.4 ~+3.8 K Nov-Dec. Images only. Host sometimes needs >10 s to connect (timeout raised to 30 s) |
| Earth Observatory Image of the Day RSS | earthobservatory.nasa.gov/feeds/image-of-the-day.rss | added (`nasa_eo_iotd`, filtered) | 200 RSS, newest 2026-09-24. The science.nasa.gov EO feed is already in `news_science_rss` |
| science.nasa.gov IOTD feed | science.nasa.gov/earth/earth-observatory/image-of-the-day/feed/ | dead | 200 HTML, 0 RSS entries |
| NASA Disasters program | disasters.nasa.gov/rss, /feed, maps.disasters.nasa.gov/arcgis/rest/services | dead | 404 on all feed / ArcGIS REST paths |
| NASA Sea Level Change portal GMSL | sealevel.nasa.gov/understanding-sea-level/key-indicators/global-mean-sea-level/ | dead | 404; climate.nasa.gov data file redirects to an HTML page |
| NASA-SSH / Sentinel-6 gridded SSH (PO.DAAC) | archive.podaac.earthdata.nasa.gov | needs key (EARTHDATA_TOKEN) | granule download needs Earthdata login; metadata used for latency only. NetCDF would also need a new dependency |
| GIBS sea surface height anomaly layers | gibs .../WMTSCapabilities.xml | dead | only TOPEX/Jason SSH layers ending 2009-06-27, 2019-01-22, 2021-04-05 |
| GIBS IMERG 30-min rain | IMERG_Precipitation_Rate_30min | added (layer `precip_imerg_30min`) | tile 200, latest 2026-09-24T08:30Z |
| GIBS IMERG monthly / precipitation anomaly | caps | dead | no such current layer (only daily IMERG, already in layers.py) |
| GIBS VIIRS flood 3-day | VIIRS_Combined_Flood_3-Day | added (layer `flood_viirs_3day`) | tile 200, 2026-09-23 and 24 |
| GIBS night lights (Black Marble / DNB) | VIIRS_NOAA20_DayNightBand_At_Sensor_Radiance | added (layer `night_lights_viirs`) | tile 200, 2026-09-23. Daily Black Marble VNP46 not in GIBS 3857; M15 composite jpeg exists but has no legend |
| GIBS OMPS aerosol index | OMPS_NOAA21_NadirMapper_AerosolIndex_380 | added (layer `aerosol_index_omps`) | tile 200, 2026-09-23 (NOAA-20/SNPP 360 nm versions stop 2025-05-05) |
| GIBS NDVI 8-day / monthly | VIIRS_NOAA20_NDVI_8Day, MODIS_Terra_L3_NDVI_Monthly | added (layers `ndvi_8day_viirs`, `ndvi_monthly_modis`) | tiles 200 on 2026-09-23 / 2026-08-01 |
| GIBS NDVI/EVI anomaly | caps | dead | no anomaly layer published |
| GIBS LST 8-day day / night | MODIS_Terra_L3_Land_Surface_Temp_8Day_Day, MODIS_Terra_Land_Surface_Temp_Night | added (layers `land_temp_8day`, `land_temp_night`) | tiles 200 on 2026-09-14 / 2026-09-23 |
| GIBS LST anomaly | caps | dead | none current |
| GIBS cloud top temperature | MODIS_Aqua_Cloud_Top_Temp_Day | added (layer `cloud_top_temp`) | tile 200, 2026-09-23 |
| GIBS SMAP sea surface salinity | SMAP_L3_Sea_Surface_Salinity_CAP_8Day_RunningMean | added (layer `sea_salinity_smap`) | tile 200, 2026-09-19 |
| GIBS SMAP soil moisture anomaly | caps | dead | no anomaly layer; root-zone SMAP L4 already in layers.py |
| GIBS fire radiative power / thermal anomalies | VIIRS_*_Thermal_Anomalies_375m_* | irrelevant | Mapbox vector tiles only in 3857; fires already come from FIRMS events |
| GIBS sea ice | - | irrelevant | not relevant to the tropics |

## Other agencies

| Candidate | URL | Verdict | Evidence |
|---|---|---|---|
| NOAA CoastWatch blended SLA (ERDDAP) | coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDsshDaily | added (`noaa_sla_regions`) | 200 CSV at 14:00 UTC; coverage to 2026-09-22; Nino 3.4 box +37.26 cm, W Pacific -7.5 cm, Gulf of Thailand +10.7 cm, Samui coast +6.1 cm. **From ~14:30 UTC the server answered 502/503 or timed out**: the collector fails fast (one request) and reports the error |
| NOAA LSA sea level time series (incl. Nino 3.4) | star.nesdis.noaa.gov/socd/lsa/SeaLevelRise/slr/slr_sla_*.csv | dead | 200 but every region's CSV ends at 2025.127 (Feb 2025) |
| PFEG ERDDAP nesdisSSH1day | coastwatch.pfeg.noaa.gov/erddap/griddap/nesdisSSH1day | dead | time_coverage_end 2026-03-25 |
| Copernicus Climate Pulse | sites.ecmwf.int/data/climatepulse/data/series/era5_daily_series_{2t_global,sst_60S-60N_ocean}.csv | added (`c3s_climate_pulse`) | 200; 2026-09-22 air 16.062 degC (+0.776, preliminary), SST 21.034 (+0.714) |
| C3S monthly climate bulletin | climate.copernicus.eu/surface-air-temperature-august-2026 | irrelevant | 200 HTML; the numbers are in Climate Pulse and the bulletins are already in `news_science_rss` (C3S RSS) |
| NOAA NCEI Climate at a Glance | ncei.noaa.gov/.../global/time-series/{globe/land_ocean,asia/land}/1/0/1850-2026/data.csv | added (`ncei_cag`) | 200; Aug 2026 globe +1.32, Asia land +1.75 (1901-2000). An end year after the current year returns 404, so the URL uses the current year. `asia/land_ocean` returns the land series anyway |
| NOAA NCEI monthly report RSS | ncei.noaa.gov/access/monitoring/monthly-report/rss.xml | added (`ncei_monthly_report`) | 200; "August 2026 Monthly Global Climate Report" 2026-09-10 |
| Met Office HadCRUT5 | metoffice.gov.uk/hadobs/hadcrut5/data/HadCRUT.5.1.0.0/.../summary_series.global.monthly.csv | added (`metoffice_hadobs`) | 200; 2026-07 = +1.097 (1961-1990). Old 5.0.2.0 file stops at 2025-02 |
| Met Office HadSST4 | metoffice.gov.uk/hadobs/hadsst4/data/data/HadSST.4.2.0.0_monthly_{GLOBE,TROP}.csv | added (same) | 200; 2026-08 globe +1.139, tropics +1.105. 4.1.1.0 URL is 404 |
| Met Office GloSea ENSO page | metoffice.gov.uk/.../gpc-outlooks/el-nino-la-nina | irrelevant | 200 but an explainer; its Nino 3.4 image is a historical series without an issue date |
| Berkeley Earth monthly | berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Land_and_Ocean_complete.txt | dead | 200 but last value 2024-12 |
| ECMWF SEAS5 Asia outlook maps | charts.ecmwf.int/opencharts-api/v1/products/seasonal_system5_standard_{rain,2mtm}/?area=ASIA | added (`ecmwf_seas5_asia`) | 200; base_time 2026-09-01; valid OND/NDJ/DJF 2026, JFM 2027; OND rain favours dry over Philippines/South China Sea |
| ECMWF SEAS5 Nino plume | .../seasonal_system5_nino_plumes | irrelevant (duplicate) | already collected by `extra_ocean.ecmwf_nino_plume` |
| ECMWF open data (GRIB) | data.ecmwf.int | irrelevant | GRIB2 needs a decoder dependency; the charts give the useful product |
| JAXA GSMaP realtime | sharaku.eorc.jaxa.jp/GSMaP | needs key | data by FTP after (free) registration; web page gives images only |
| JAXA Earth API (STAC COG) | s3.ap-northeast-1.wasabisys.com/je-pds/cog/v1/catalog.json | irrelevant (for now) | 200 keyless, but Cloud-Optimized GeoTIFFs need a raster dependency; GSMaP there is climatology only (normals) |
| JAXA Himawari monitor | - | irrelevant | Himawari IR is already in layers.py via GIBS |
| BoM FTP (non-SOI products) | ftp.bom.gov.au/anon/home/ncc/www/sco/ | dead | only `ahead` and `grids` from 2015 plus `soi` (already used) |
| APCC ENSO outlook | apcc21.org/prediction/global/enso | blocked | JavaScript app; ENSO section links to an SSO sign-in |
| CMA / BCC ENSO | cmdp.ncc-cma.net/pred/cn_enso_forecast.php, /download/ENSO/Monitor/nino_monthly.txt | dead | 404 |
| IMD ENSO / IOD bulletin | mausam.imd.gov.in/responsive/enso.php, imdpune.gov.in/cmpg/Products/ENSO_IOD.php | dead | 404 |
| KMA | weather.go.kr | irrelevant | no English machine-readable ENSO product found |
| Climate Reanalyzer | - | irrelevant | already collected (`cr_world_sst`, `cr_nino34_daily`) |

## Credentials

None of the added collectors needs a credential. `EARTHDATA_TOKEN` (env, read with
`os.environ` in extra_nasa.py, helper `earthdata_token()`) would only be needed to download
Earthdata granules (PO.DAAC NASA-SSH / Sentinel-6 grids, GPM files); no collector does that
yet, so nothing shows `needs_config`.
