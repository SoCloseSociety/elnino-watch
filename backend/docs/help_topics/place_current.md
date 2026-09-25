# Current conditions (model analysis) and forecast badges
id: place_current
short: The "now" values are Open-Meteo model analyses for the place (not a weather station). Future days are marked Forecast. Every value shows its time and source.
category: data
related: model_vs_observation, open_meteo, era5, freshness, stale_data
aliases: current conditions, observed, forecast badge, model

## What it is

Badges tell you what kind of number you are looking at:

- **Model**: a model analysis for the current hour, the best estimate for the exact point, not a thermometer reading.
- **Forecast**: a value for a future date; it changes with each update (every few hours).
- **Reanalysis**: ERA5, observations blended by a model after the fact, about 5 days behind.
- **Observed**: satellite fire detections, earthquakes.
- **Bulletin**: an official warning text.

Feels-like temperature combines air temperature, humidity and wind (heat index in the tropics, wind chill in the cold).

## Why it matters for Koh Samui

Comparing a Thai noon with a Russian night is misleading: the card shows each place's local time. Look at the 7-day range rather than a single hour.

## Sources

- [Open-Meteo -- weather forecast API](https://open-meteo.com/en/docs)
