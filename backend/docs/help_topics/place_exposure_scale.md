# Comparison matrix: exposure scores (0-4)
id: place_exposure_scale
short: Each cell scores how exposed a place is to one hazard over the long term, 0 very low to 4 very high, with the value, the rule used, a note and the source.
category: hazards
related: place_ranking, place_coverage, climatology_baseline, era5
aliases: matrix, exposure, comparison matrix, very low, very high

## What it is

The matrix uses long-term data only: the 1991-2020 climate normals (ERA5), the 2050 projections (CMIP6), the earthquake record since 1976 (USGS), a year of modelled air quality (CAMS) and the curated El Nino sensitivity. Today's weather does not change it.

Hover or tap a cell for its value, rule and note. Cells without data say so and are left out of the ranking.

Rows: Heat stress (days with feels-like above 35 C), Cold / winter severity, Water / drought (aridity), Flood (heavy rain, river, coast), Storms / cyclones, Air quality (PM2.5, yearly mean), Wildfire (fire-weather months), Earthquakes (USGS record since 1976), ENSO sensitivity (how much El Nino reaches a place), Climate trend to 2050 (CMIP6), Data coverage per place.

## How to read it

Columns: Score | Label | Colour

- 0 | very low | green
- 1 | low | yellow
- 2 | moderate | orange
- 3 | high | red
- 4 | very high | magenta
- -- | no data | grey, dashed

Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## Why it matters for Koh Samui

It shows trade-offs at a glance: one place is hot, another cold, a third far from the sea but on a river.

## Sources

- [Open-Meteo -- historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo -- climate change API (CMIP6 HighResMIP)](https://open-meteo.com/en/docs/climate-api)
