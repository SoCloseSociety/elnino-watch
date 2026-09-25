# Heat stress (days with feels-like above 35 C)
id: place_heat_stress
short: How many days a year the feels-like maximum exceeds 35 C (ERA5, 1991-2020 average). Humid tropical places score high even when the air temperature looks moderate.
category: hazards
related: heat_index, place_trend_2050, place_exposure_scale
aliases: heat days, heat stress, hot days

## What it is

Counted from ERA5 daily feels-like (apparent) maximum temperature, averaged over 1991-2020. Feels-like uses temperature, humidity and wind, so humid heat counts more than dry heat.

## How to read it

Columns: Heat days per year | Exposure

- < 5 | 0 very low
- 5-30 | 1 low
- 30-90 | 2 moderate
- 90-180 | 3 high
- >= 180 | 4 very high

Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## Why it matters for Koh Samui

Heat stress affects sleep, health (especially for older people and children), work and electricity bills for air conditioning. El Nino years add heat in Southeast Asia.

## Sources

- [Open-Meteo -- historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
- [US National Weather Service -- Heat index](https://www.weather.gov/ama/heatindex)
