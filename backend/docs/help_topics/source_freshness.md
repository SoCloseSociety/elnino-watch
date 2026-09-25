# Data freshness and the "stale" state

id: source_freshness
short: A source can answer correctly and still serve old data. "Stale" means the newest value is older than it should be.

## What it is
Every source has two separate health checks. **Fetch**: did the last request work
(ok, error, needs configuration)? **Freshness**: how old is the newest piece of data
it gave us? Each source declares the oldest its newest data may be ("max age") and
where that date lives: the newest measurement, the newest article, the newest map
event, or simply the last successful fetch for forecasts.

## How to read it
- **ok**: the fetch worked and the data is recent enough.
- **stale**: the fetch worked, but the newest data is older than the max age. Treat
  its numbers as history, not as "now".
- **error / needs_config / empty / pending**: the fetch itself failed, needs a key,
  returned nothing, or has not run yet.
- The age shown is "newest data" to "now". Examples of max age: ONI 90 days (a
  3-month average published about 7 weeks after its middle month), weekly Nino SST
  12 days, daily SST 4 days, GDACS disasters 1 hour, news 2 days, social posts 1 day.
- **expected** (a dashed chip next to a stale source): the source is known to be
  silent and the reason is written next to it (the climate.gov ENSO blog has not
  published since June 2025). The state stays "stale" because the data really is old,
  but it is not counted in the header's stale badge and the source check script does
  not fail on it.

## Why it matters for Koh Samui
A decision about Koh Samui should never rest on a number that looks current but is
weeks old. Example: the climate.gov ENSO blog feed still answers normally, but its
last post is from June 2025, so it shows as stale.

## Limits
Monthly indices are slow by nature: an ONI that is 70 days old is normal, not broken.
"Stale" says the data is old, not that it is wrong. A source quiet by design (warning
pages that only publish when there is weather) is judged on its last successful fetch.

## Sources
- NOAA CPC ONI table and release cadence: https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php
- climate.gov ENSO blog (example of a stale feed): https://www.climate.gov/news-features/department/enso-blog
