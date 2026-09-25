# Wildfire (fire-weather months)
id: place_wildfire
short: A climate proxy: months per year that are both warm (mean max >= 20 C) and dry (rain below half of evaporation). Current satellite fire detections are in the place level.
category: hazards
related: firms_fires, place_air
aliases: wildfire, forest fire, fire weather

## What it is

A long fire record needs the NASA FIRMS archive, which requires a key, so the long-term score uses the climate normals as a proxy for the length of the fire-weather season. It says nothing about fuel (forests, grass) or ignition. Live detections within 100 km (VIIRS, last 24 h) are shown in the Wildfire factor of each place.

## How to read it

Columns: Warm and dry months per year | Exposure

- 0 | 0
- 1-2 | 1
- 3-4 | 2
- 5-6 | 3
- >= 7 | 4

Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## Why it matters for Koh Samui

Wildfire smoke travels hundreds of km (Samui haze comes from fires elsewhere); nearby fires threaten homes and roads.

## Sources

- [NASA FIRMS -- active fires](https://firms.modaps.eosdis.nasa.gov/)
- [Open-Meteo -- historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
