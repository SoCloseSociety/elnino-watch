"""Additional NASA GIBS map layers (same shape as app.layers.LAYERS entries).

Exported as EXTRA_LAYERS for the lead to merge into the layer list. Every entry was checked
on 2026-09-24 against the live GIBS WMTS capabilities (epsg3857/best): identifier, tile
matrix set (max zoom), image format, time dimension and the horizontal legend URL come from
the capabilities document, and a z3 tile over SE Asia (x=6, y=3) returned HTTP 200 with an
image for the date in `verified`. None duplicates app.layers.LAYERS.

Checked and not added (see backend/docs/NASA_AGENCIES.md):
- Sea surface height anomaly: the GIBS SSH layers stop in 2009-2021 (no current layer);
  sea level comes in as numbers from NOAA CoastWatch instead (collector noaa_sla_regions).
- Fire radiative power / thermal anomalies: vector tiles only in EPSG:3857 (fires are map
  events from FIRMS already).
- NDVI / precipitation anomaly, GRACE groundwater: no current GIBS layer exists (GRACE maps
  come in as images from collector nasa_grace_drought).
"""

from __future__ import annotations

from .layers import GIBS_LEGEND, _gibs

EXTRA_LAYERS: list[dict] = [
    {
        "id": "precip_imerg_30min", "gibs_id": "IMERG_Precipitation_Rate_30min",
        "title": "Rain right now (GPM IMERG, 30-minute)",
        "url_template": _gibs("IMERG_Precipitation_Rate_30min", 6, "png", timed=False),
        "max_zoom": 6, "format": "png", "time_mode": "latest", "default_date_offset_days": None,
        "legend_url": GIBS_LEGEND.format(name="GPM_Precipitation_Rate"),
        "attribution": "NASA GIBS / GPM IMERG Early (30 min)",
        "description": (
            "Satellite rain estimate for the latest half hour (about 4-6 hours behind real "
            "time), in mm per hour on a scale from 0.1 to 53: pale colours are light rain "
            "(under 1 mm/h), the strongest colours heavy downpours (over 10-20 mm/h). Covers "
            "the sea too, where there is no radar."),
        "verified": {"date": "latest (2026-09-24T08:30Z)", "http": 200, "latency_ms": 1672},
    },
    {
        "id": "flood_viirs_3day", "gibs_id": "VIIRS_Combined_Flood_3-Day",
        "title": "Flood water (VIIRS, 3-day composite)",
        "url_template": _gibs("VIIRS_Combined_Flood_3-Day", 9, "png"),
        "max_zoom": 9, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True,
        "legend_url": GIBS_LEGEND.format(name="MODIS_Flood"),
        "attribution": "NASA GIBS / LANCE VIIRS flood product (NOAA-20 + NOAA-21)",
        "description": (
            "Land covered by water that is not normally there, detected by satellite over "
            "the last 3 days (combining days fills cloud gaps). Red = flood, yellow = "
            "recurring (seasonal) flood, light blue = normal surface water, grey = "
            "insufficient data (clouds). No red does not prove no flood."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1436},
    },
    {
        "id": "night_lights_viirs", "gibs_id": "VIIRS_NOAA20_DayNightBand_At_Sensor_Radiance",
        "title": "Night lights (VIIRS Day/Night Band)",
        "url_template": _gibs("VIIRS_NOAA20_DayNightBand_At_Sensor_Radiance", 8, "png"),
        "max_zoom": 8, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True,
        "legend_url": GIBS_LEGEND.format(name="VIIRS_DayNightBand_At_Sensor_Radiance"),
        "attribution": "NASA GIBS / NOAA-20 VIIRS Day/Night Band",
        "description": (
            "Last night's light seen from space (radiance, 0 to about 38 nW/cm2/sr). Bright "
            "spots are towns, ports and fishing fleets. A town that goes dark on a clear night after a storm suggests a power "
            "cut. Clouds and moonlight also dim or brighten the picture, so compare several "
            "nights."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1595},
    },
    {
        "id": "aerosol_index_omps", "gibs_id": "OMPS_NOAA21_NadirMapper_AerosolIndex_380",
        "title": "Smoke and dust index (OMPS UV aerosol index)",
        "url_template": _gibs("OMPS_NOAA21_NadirMapper_AerosolIndex_380", 6, "png"),
        "max_zoom": 6, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True,
        "legend_url": GIBS_LEGEND.format(name="OMPS_Aerosol_Index"),
        "attribution": "NASA GIBS / NOAA-21 OMPS Nadir Mapper",
        "description": (
            "Ultraviolet index of light-absorbing smoke and dust, seen even above clouds. "
            "Scale below 0 to 5 and above: values above about 1 mean smoke or dust is present, "
            "above 2-3 thick smoke, e.g. from fires in Sumatra and Borneo in El Nino "
            "years. Complements the aerosol optical depth layer."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1914},
    },
    {
        "id": "ndvi_8day_viirs", "gibs_id": "VIIRS_NOAA20_NDVI_8Day",
        "title": "Vegetation greenness (NDVI, rolling 8 days)",
        "url_template": _gibs("VIIRS_NOAA20_NDVI_8Day", 8, "png"),
        "max_zoom": 8, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "legend_url": GIBS_LEGEND.format(name="MODIS_NDVI"),
        "attribution": "NASA GIBS / NOAA-20 VIIRS NDVI (rolling 8-day)",
        "description": (
            "How green and healthy plants are (NDVI from 0 = bare ground to about 0.8-0.9 = "
            "dense green). Browner shades where you would expect green (rice fields, plantations) is a "
            "sign of drought stress. Compare with the same place a few weeks earlier."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1738},
    },
    {
        "id": "ndvi_monthly_modis", "gibs_id": "MODIS_Terra_L3_NDVI_Monthly",
        "title": "Vegetation greenness (NDVI, monthly)",
        "url_template": _gibs("MODIS_Terra_L3_NDVI_Monthly", 7, "png"),
        "max_zoom": 7, "format": "png", "time_mode": "daily", "default_date_offset_days": 55,
        "legend_url": GIBS_LEGEND.format(name="MODIS_L3_NDVI"),
        "attribution": "NASA GIBS / Terra MODIS NDVI (monthly, MOD13C2)",
        "description": (
            "Cloud-free monthly greenness, dated the 1st of the month it covers. Good for "
            "comparing this El Nino dry season with the same month of other years. Scale "
            "0 (bare) to 1: brown shades = sparse or stressed vegetation, dark green = dense."),
        "verified": {"date": "2026-08-01", "http": 200, "latency_ms": 1895},
    },
    {
        "id": "land_temp_8day", "gibs_id": "MODIS_Terra_L3_Land_Surface_Temp_8Day_Day",
        "title": "Land surface temperature (day, 8-day, cloud-free)",
        "url_template": _gibs("MODIS_Terra_L3_Land_Surface_Temp_8Day_Day", 7, "png"),
        "max_zoom": 7, "format": "png", "time_mode": "daily", "default_date_offset_days": 12,
        "legend_url": GIBS_LEGEND.format(name="MODIS_Land_Surface_Temp"),
        "attribution": "NASA GIBS / Terra MODIS LST (MOD11A2, 8-day)",
        "description": (
            "Daytime ground temperature averaged over 8 days, so tropical clouds leave fewer "
            "holes than in the daily layer. The legend is in kelvin (K): 300 K = 27 degC, "
            "310 K = 37 degC, 320 K = 47 degC. This is the ground, not the air: in the sun "
            "it runs hotter than the forecast air temperature."),
        "verified": {"date": "2026-09-14", "http": 200, "latency_ms": 1900},
    },
    {
        "id": "land_temp_night", "gibs_id": "MODIS_Terra_Land_Surface_Temp_Night",
        "title": "Land surface temperature (night, MODIS)",
        "url_template": _gibs("MODIS_Terra_Land_Surface_Temp_Night", 7, "png"),
        "max_zoom": 7, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True,
        "legend_url": GIBS_LEGEND.format(name="MODIS_Land_Surface_Temp"),
        "attribution": "NASA GIBS / Terra MODIS LST (night pass)",
        "description": (
            "Night-time ground temperature (legend in kelvin: 295 K = 22 degC, 300 K = 27 "
            "degC). Warm nights (little cooling) are what make heat waves dangerous for "
            "health. Gaps are clouds."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1469},
    },
    {
        "id": "cloud_top_temp", "gibs_id": "MODIS_Aqua_Cloud_Top_Temp_Day",
        "title": "Cloud top temperature (MODIS Aqua, afternoon)",
        "url_template": _gibs("MODIS_Aqua_Cloud_Top_Temp_Day", 6, "png"),
        "max_zoom": 6, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True,
        "legend_url": GIBS_LEGEND.format(name="MODIS_Cloud_Top_Temp"),
        "attribution": "NASA GIBS / Aqua MODIS cloud product",
        "description": (
            "Temperature at the top of clouds, in kelvin (legend 150-350 K). The coldest "
            "tops, below 220-230 K (about -50 degC, purple/magenta and dark blue), are tall "
            "thunderstorm towers; El Nino moves these storms from Southeast Asia toward the "
            "central Pacific. For the live picture use the Himawari infrared layer."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1933},
    },
    {
        "id": "sea_salinity_smap", "gibs_id": "SMAP_L3_Sea_Surface_Salinity_CAP_8Day_RunningMean",
        "title": "Sea surface salinity (SMAP, 8-day)",
        "url_template": _gibs("SMAP_L3_Sea_Surface_Salinity_CAP_8Day_RunningMean", 6, "png"),
        "max_zoom": 6, "format": "png", "time_mode": "daily", "default_date_offset_days": 5,
        "legend_url": GIBS_LEGEND.format(name="SMAP_Sea_Surface_Salinity"),
        "attribution": "NASA GIBS / SMAP L3 sea surface salinity (JPL CAP)",
        "description": (
            "Saltiness of the sea surface in practical salinity units (legend 30-40 PSU; "
            "open ocean is about 34-35). Fresher water marks heavy rain and river outflow; during El Nino the fresh pool "
            "under the rain band shifts east across the Pacific. Coastal values within about "
            "40 km of land are less reliable."),
        "verified": {"date": "2026-09-19", "http": 200, "latency_ms": 1337},
    },
]

EXTRA_LAYERS_BY_ID = {x["id"]: x for x in EXTRA_LAYERS}
