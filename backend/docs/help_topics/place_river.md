# River discharge (GloFAS)
id: place_river
short: Daily river flow in m3/s from the Copernicus GloFAS model for the largest river cell near the place, compared with its 2001-2020 flood levels.
category: hazards
related: place_flood, place_levels
aliases: GloFAS, river discharge, m3/s, 2-year flood

## What it is

GloFAS is a global hydrological model on a 5 km grid. For each place we search 7 x 7 cells (about 15 km) and keep the one with the largest flow, then compute from 2001-2020:

- the 99th percentile of daily flow,
- the **2-year flood** (median of the yearly maxima),
- the **10-year flood** (90th percentile of the yearly maxima).

The forecast (30 days, ensemble) is compared with these levels. Model flows can differ from gauges, especially for small or regulated rivers and estuaries.

## Why it matters for Koh Samui

Spring snowmelt floods (Russia) and long rainy spells (Normandy) show up here days to weeks ahead.

## Sources

- [Open-Meteo -- flood API (GloFAS)](https://open-meteo.com/en/docs/flood-api)
