# Observed, forecast, model analysis, reanalysis, bulletin

id: value_kind
short: Every number says what kind of value it is: measured, predicted, modelled or announced.

## What it is
Each factor, exit signal, latest value and status document carries a `kind`:
- **observed**: measured by a station, gauge, buoy or satellite, or an index computed from measurements (ONI, RONI, weekly Nino 3.4, SOI, MEI, Degree Heating Weeks, Air4Thai PM2.5).
- **forecast**: a model prediction. Today's daily total or maximum is also a forecast, because the day is not over.
- **model_analysis**: a weather model's own estimate of a past hour or day (Open-Meteo past days, CAMS air quality before now). Not a measurement.
- **reanalysis**: ERA5, past weather rebuilt from all observations by a model, about 5 days behind. Used against the 1991-2020 normal.
- **bulletin**: an agency statement (NOAA CPC status, TMD warning, PWA notice, GDACS alert).

## How to read it
A forecast never has an 'observed' date: its `observed_at` is empty and `valid_for` gives the day it predicts. For example 'forecast max feels-like 37.2 °C on Wed 30 Sep (Open-Meteo, fetched 24 Sep 20:09 ICT)' is a prediction made on 24 September for 30 September.

## Why it matters for Koh Samui
A measured flood and a forecast of rain call for different actions. Mixing them up can make you act too late or panic for nothing.

## Limits
Model analyses and reanalyses are smoothed over 25-50 km grid cells: they miss local showers. Only the ThaiWater gauges and Air4Thai stations are true local measurements, and Koh Samui has no Air4Thai station.

## Sources
- https://open-meteo.com/en/docs
- https://open-meteo.com/en/docs/historical-weather-api
- https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/
