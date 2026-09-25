# Data coverage per place
id: place_coverage
short: How many of the 10 ranked dimensions have data for a place. Long-term data (normals, projections, river levels) is computed once and filled over a few days.
category: data
related: data_coverage, freshness, place_ranking
aliases: coverage, missing data

## What it is

Heavy one-time downloads (30 years of ERA5, CMIP6 projections, GloFAS history) are spread over several scheduler runs so they never exhaust the shared Open-Meteo quota that the Koh Samui watch also uses. Until then those cells say "no data yet". Coverage is shown in the matrix but not used in the ranking.

## Sources

- [Open-Meteo -- historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
