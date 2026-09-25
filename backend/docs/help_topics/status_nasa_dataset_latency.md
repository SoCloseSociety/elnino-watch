# NASA dataset freshness

id: status_nasa_dataset_latency
short: Newest file time and lag of 11 NASA datasets behind our maps.

## What it is
Status key nasa_dataset_latency {checked_at, datasets: [{id, title, time_end, lag_h, late, why}]}.

## How to read it
lag_h = hours between the end of the newest data and the check. late = true when the lag exceeds the normal delay for that product.

## Why it matters for Koh Samui
Explains a stale map: NASA itself may be behind.

## Limits
Metadata only.

## Sources
- https://cmr.earthdata.nasa.gov/search/
