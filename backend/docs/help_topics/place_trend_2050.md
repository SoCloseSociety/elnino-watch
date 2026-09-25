# Climate trend to 2050 (CMIP6)
id: place_trend_2050
short: Change between 1991-2020 and 2036-2050 in mean temperature and hot days (> 35 C), from 6 high-resolution climate models on a high-emission pathway. The model range is shown.
category: forecasts
related: place_projection, place_heat_stress, place_cold
aliases: 2050, climate change, projection, CMIP6, warming

## What it is

The Open-Meteo climate API gives daily data from 6 CMIP6 HighResMIP models, bias-corrected on ERA5-Land (10 km). Their future forcing is as close to the high-emission RCP8.5 / SSP5-8.5 pathway as CMIP6 allows; before 2050 the scenarios differ little. The daily mean is taken as (max + min) / 2. Hot day = model daily maximum above 35 C (air temperature, not feels-like).

## How to read it

Columns: Warming (ensemble mean) | Exposure

- < 0.75 C | 0
- 0.75-1.25 C | 1
- 1.25-1.75 C | 2
- 1.75-2.5 C | 3
- >= 2.5 C | 4

At least 2 if hot days rise by 10 or more per year, at least 3 if by 30 or more. Fewer frost days are shown but not scored. Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## Why it matters for Koh Samui

A home is for decades. Warming reduces cold hazards in Russia but adds heat everywhere, most painfully where it is already hot and humid.

## Sources

- [Open-Meteo -- climate change API (CMIP6 HighResMIP)](https://open-meteo.com/en/docs/climate-api)
