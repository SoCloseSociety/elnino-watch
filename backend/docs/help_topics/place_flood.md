# Flood (heavy rain, river, coast)
id: place_flood
short: The worst of three parts: days with 50 mm of rain or more, the height of the place above the nearest large river (GloFAS), and low-lying coast.
category: hazards
related: place_river, place_levels
aliases: flood, river, storm surge, heavy rain days

## What it is

- **Heavy rain**: ERA5 days per year with >= 50 mm. ERA5 is a ~30 km model and smooths peaks: real local downpours are stronger.
- **River**: the largest river cell (mean flow >= 1 m3/s) within about 15 km, from GloFAS. What matters is how far the place sits above it: a hilltop village above an estuary is not exposed to river floods.
- **Coast**: when a sea cell is within 10 km and the place is low (elevation from the Copernicus DEM).

See River discharge (GloFAS) for the river forecast.

## How to read it

Columns: Part | 1 | 2 | 3 | 4

- Heavy-rain days/yr | 0.5-2 | 2-5 | 5-10 | >= 10
- Height above river cell | < 30 m | < 10 m | < 3 m | --
- Coastal and elevation | < 20 m | < 10 m | < 5 m | --

Score = the highest part. Elevations are at the place point: individual streets can be lower. Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## Why it matters for Koh Samui

Floods damage homes, cut roads and ferries, and contaminate water. Check the exact plot before buying or renting.

## Sources

- [Open-Meteo -- historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo -- flood API (GloFAS)](https://open-meteo.com/en/docs/flood-api)
- [Open-Meteo -- marine weather API](https://open-meteo.com/en/docs/marine-weather-api)
