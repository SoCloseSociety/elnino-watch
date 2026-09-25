# Water factor: sources and fallbacks

id: water_fallback
short: ERA5 rain vs normal first; if ERA5 is missing, the forecast model's own past-day analyses; plus PWA notices, the dam and the seasonal forecast.

## What it is
The level comes from rain over 90 days (180 in the dry season) as a percentage of the 1991-2020 ERA5 normal. If the ERA5 archive is missing or more than 10 days behind, the app uses Open-Meteo's past-day model analyses against the same normal and says so. PWA Ko Samui notices, the Ratchaprapa dam (mainland, regional only) and the ECMWF SEAS5 3-month forecast can raise the level.

## How to read it
The factor's `kind` is 'reanalysis' with ERA5 and 'model_analysis' with the fallback. Model analyses usually run wetter than ERA5 at this grid cell, so the fallback understates a deficit rather than inventing one.

## Why it matters for Koh Samui
Samui's water comes from small reservoirs, desalination and a mainland pipeline; rationing started on 3 August 2026 after a dry spell.

## Limits
The island's own reservoir levels and the PWA rotation schedule are not published in machine-readable form. Check them on the PWA notices page (branch Ko Samui) or call PWA 1662.

## Sources
- https://www.pwa.co.th/news/call1662
- https://open-meteo.com/en/docs/historical-weather-api
- https://www.thaiwater.net/
