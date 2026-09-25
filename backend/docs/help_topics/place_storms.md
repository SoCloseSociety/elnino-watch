# Storms / cyclones
id: place_storms
short: Days per year with gusts of 75 km/h or more (ERA5 1991-2020). Tropical-cyclone history is added to the note with sources.
category: hazards
related: gdacs, place_levels
aliases: wind, gusts, storms, typhoon, cyclone

## What it is

ERA5 gusts are for a ~30 km cell and underestimate local gusts on exposed coasts and hills. Tropical cyclones are rare events that 30 years of gust statistics do not capture well, so documented landfalls near a place are listed in the note (for Maenam: Typhoon Gay 1989 and Tropical Storm Pabuk 2019). Current cyclones come from GDACS in the place level.

## How to read it

Columns: Gust days (>= 75 km/h) per year | Exposure

- < 0.5 | 0
- 0.5-2 | 1
- 2-5 | 2
- 5-15 | 3
- >= 15 | 4

Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## Why it matters for Koh Samui

Storms cut power, block roads and ferries and damage roofs. On an island they can isolate you for days.

## Sources

- [Open-Meteo -- historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
- [GDACS -- Global Disaster Alert and Coordination System](https://www.gdacs.org/)
