# Cold / winter severity
id: place_cold
short: Scored from the mean temperature of the coldest month (ERA5 1991-2020), with frost days and yearly snowfall in the note.
category: hazards
related: place_levels, place_trend_2050
aliases: cold, winter, frost days, snow

## What it is

The coldest month mean summarises how hard winter is: heating needs, frozen roads, snow clearing. Frost days = days with a minimum below 0 C. Snowfall is in cm of fresh snow per year.

## How to read it

Columns: Coldest month mean | Exposure

- >= 10 C | 0 very low
- 3 to 10 C | 1 low
- -3 to 3 C | 2 moderate
- -10 to -3 C | 3 high
- < -10 C | 4 very high

Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## Why it matters for Koh Samui

Cold is a real hazard for health, housing (insulation, heating fuel) and daily life, and a big change for anyone used to the tropics.

## Sources

- [Open-Meteo -- historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
- [US National Weather Service -- Wind chill chart](https://www.weather.gov/safety/cold-wind-chill-chart)
