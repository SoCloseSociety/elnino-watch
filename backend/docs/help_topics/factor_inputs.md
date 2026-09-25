# The numbers behind a factor (inputs)

id: factor_inputs
short: Each factor lists every number it used, each with its own kind, date and source.

## What it is
`inputs` is a list of {name, value, unit, unit_label, kind, valid_for, tz, issued_at, retrieved_at, source, url, note}. The water factor, for instance, lists the 30/60/90/180-day ERA5 rain percentages, the ECMWF seasonal forecast, the Ratchaprapa dam level and the PWA notice count.

## How to read it
The headline value of a factor is the one that sets its level (for El Nino, the weekly Nino 3.4 when it is stronger than the 3-month RONI). The inputs show the rest, so you can check each number against its source link.

## Why it matters for Koh Samui
You can see whether a level comes from a measurement, a forecast or an agency warning before deciding what to do.

## Limits
Inputs are what the app stored at the last evaluation (every scheduler round, at most a few minutes old).

## Sources
- https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml
- https://open-meteo.com/en/docs
