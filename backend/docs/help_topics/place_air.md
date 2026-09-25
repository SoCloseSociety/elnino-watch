# Air quality (PM2.5, yearly mean)
id: place_air
short: Mean PM2.5 over the last 365 days from the global CAMS model (the same model for every place), against the WHO 2021 guideline and interim targets.
category: hazards
related: pm25, aqi, cams, place_levels
aliases: PM2.5, air pollution, haze, pollen

## What it is

PM2.5 are fine particles (smoke, traffic, industry, dust) that reach the lungs and blood. The yearly mean comes from the CAMS global model so that all places are compared with the same tool; it is a model, not a monitoring station.

The note gives the number of days above the WHO 24-hour guideline (15 ug/m3) and above 37.5 ug/m3. In Europe the place card also shows CAMS pollen (alder, birch, grass, mugwort, olive, ragweed).

## How to read it

Columns: Yearly mean PM2.5 | WHO 2021 | Exposure

- <= 5 | guideline | 0
- 5-10 | interim target 4 | 1
- 10-15 | interim target 3 | 2
- 15-25 | interim target 2 | 3
- > 25 | above IT-2 | 4

Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## Why it matters for Koh Samui

Southeast Asia has a smoke season (February-April) that El Nino makes worse; European villages are usually cleaner but can have pollen seasons.

## Sources

- [WHO global air quality guidelines (2021)](https://www.who.int/publications/i/item/9789240034228)
- [Open-Meteo -- air quality API (CAMS)](https://open-meteo.com/en/docs/air-quality-api)
