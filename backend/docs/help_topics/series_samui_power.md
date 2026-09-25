# Samui daily weather from NASA POWER

id: series_samui_power
short: samui_power_t2m, _t2m_max, _t2m_min, _t2m_anom, _precip, _rh, _wind10m, _solar.

## What it is
Daily values for the Samui grid cell from NASA POWER: mean, maximum and minimum air temperature at 2 m, rain, relative humidity, wind at 10 m and sunshine energy. samui_power_t2m_anom is the daily mean minus the 2001-2020 mean of that month.

## How to read it
degC, mm, %, m/s, kWh/m2/day. A run of positive anomalies = warmer than usual; rain is best read as 30-day totals (status samui_power).

## Why it matters for Koh Samui
Independent check on the Open-Meteo numbers used by the risk engine.

## Limits
Grid-cell values (about 50 km), smoother than a real station.

## Sources
- https://power.larc.nasa.gov/
- https://power.larc.nasa.gov/docs/methodology/
