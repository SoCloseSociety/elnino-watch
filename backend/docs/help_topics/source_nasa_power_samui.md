# NASA POWER for Koh Samui

id: source_nasa_power_samui
short: NASA's daily satellite-and-model weather for the Samui grid cell, with 2001-2020 normals.

## What it is
NASA Langley's POWER service combines the MERRA-2 / GEOS-IT weather reanalysis with CERES satellite sunshine data. The app asks it twice a day for the last 60 days of temperature, rain, humidity, wind and sunshine at 9.512 N 100.013 E, and for the 2001-2020 monthly normals of the same place.

## How to read it
Values are daily, in local solar time: degC, mm of rain, % humidity, m/s wind, and kWh per m2 per day of sunshine. Temperature and rain arrive about 2-3 days late, sunshine about 5-7 days late. Missing days are simply absent (NASA marks them -999 and the app never stores those).

## Why it matters for Koh Samui
It is an independent second source next to Open-Meteo/ERA5: if both say the last weeks were drier and hotter than normal, the signal is solid. In El Nino years Samui often gets a weaker, later rainy season (normally October-December).

## Limits
One grid cell is about 50 km across and mixes sea and land, so it smooths out the island's own showers and hottest afternoons. Use trends, not single days.

## Sources
- https://power.larc.nasa.gov/
- https://power.larc.nasa.gov/docs/services/api/
