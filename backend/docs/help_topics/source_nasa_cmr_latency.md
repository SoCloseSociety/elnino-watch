# NASA dataset freshness (CMR)

id: source_nasa_cmr_latency
short: How many hours old the newest file of each key NASA dataset is.

## What it is
NASA's catalogue (CMR) lists every file (granule) of every dataset. Every 3 hours the app asks for the newest one of 11 datasets behind our maps and series: MUR and OISST sea temperature, GPM IMERG rain, SMAP soil moisture, GRACE-FO water storage, Sentinel-6 and NASA-SSH sea level.

## How to read it
For each dataset: the time its newest data ends, the lag in hours, and 'late' when the lag is beyond what is normal for that product (e.g. 12 h for 30-minute rain, 72 h for daily sea temperature, months for GRACE).

## Why it matters for Koh Samui
When a map layer looks old, this tells you whether it is NASA that is behind (nothing to fix here) or our app.

## Limits
It checks metadata only, not the files themselves. GRACE products are by design months behind.

## Sources
- https://cmr.earthdata.nasa.gov/search/
- https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
