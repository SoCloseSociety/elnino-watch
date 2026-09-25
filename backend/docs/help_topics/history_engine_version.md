# Level history and engine versions

id: history_engine_version
short: Each history point records the engine version; points from before the 24 Sep 2026 audit are annotated.

## What it is
`/api/local/history` rows are {evaluated_at, level, level_key, engine_version, note?}. Version 3 (from 24 September 2026) labels every value as observed / forecast / model analysis / reanalysis / bulletin. Rows written by version 2 keep their level (it was computed with the same thresholds) and carry a note saying that engine did not label forecasts.

## How to read it
The level line is continuous across versions; the note only warns that older explanations may have called a forecast date 'observed'.

## Why it matters for Koh Samui
Nothing in the history is rewritten after the fact, and nothing misleading is shown without a warning.

## Limits
The history keeps the last 1000 points (a new point when the level changes, otherwise every 30 minutes).

## Sources
- https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/
