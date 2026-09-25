# Valid for, time zones, as of

id: valid_for
short: The day or period a value describes, and the clock used (Samui time or UTC).

## What it is
- `valid_for`: the date (YYYY-MM-DD) or period (start/end, both days included) the value describes. The 90-day rain window '2026-06-21/2026-09-18' covers 21 June to 18 September; the weekly Nino 3.4 of 16 Sep covers the week 13-19 Sep; ONI/RONI 'JJA 2026' covers 1 June-31 August.
- `tz`: 'ICT (UTC+7)' for Samui's local days (weather, sea, rain), 'UTC' for global indices, satellites and cyclone positions.
- `issued_at`: when an agency published it (bulletins, the IRI forecast).
- `retrieved_at`: when this app fetched it (for forecasts, the best available stand-in for the model run time).
- `as_of`: the single time shown next to a value: the observation time, else the issue time, else the fetch time.

## How to read it
'Rain 103% of normal (90 d to 18 Sep)' means the 90 days ending on 18 September, Samui time. A value whose `as_of` is old is marked stale.

## Why it matters for Koh Samui
ERA5 rain runs about 5 days behind and ONI is a 3-month average: they describe the past, not today. The date tells you how current the picture is.

## Limits
Open-Meteo does not publish the run time of its blended forecast, so the fetch time is shown instead.

## Sources
- https://www.cpc.ncep.noaa.gov/data/indices/
- https://open-meteo.com/en/docs
