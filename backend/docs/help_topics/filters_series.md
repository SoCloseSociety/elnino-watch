# Chart data filters (date range and downsampling)

id: filters_series
short: Charts can load only a date range, or a lighter version of long series (one average per day, or every Nth point).

## What it is
Options when a chart loads a series: "since" and "until" dates, and "downsample":
`daily` (one average value per day) or a number N (keep every Nth point; the most
recent point is always kept). The series list can be filtered by source, source
category (ocean index, maritime, local, ...) or name.

## How to read it
A daily average smooths hourly buoy data: peaks within a day are flattened. Every-Nth
keeps real measured values but skips the ones in between.

## Why it matters for Koh Samui
Some series are large (hourly buoy temperatures, 40 years of weekly SST). Lighter
charts load faster, especially on a phone on island internet.

## Limits
Do not read extremes from a downsampled chart; load the full range for that. A daily
average of a series that has one value per day is the value itself.

## Sources
- NOAA CPC weekly Nino SST data (a long series): https://www.cpc.ncep.noaa.gov/data/indices/
