# Ranking and weights (decision aid)
id: place_ranking
short: Score = weighted average of (4 - exposure) over the dimensions that have data, shown as 0-100. You set the weights; by default all are equal. A decision aid only.
category: data
related: place_exposure_scale, place_coverage, place_advisories
aliases: ranking, weights, sliders, score

## What it is

How it is computed, with nothing hidden:

- For each place and dimension, suitability = 4 - exposure score (so 4 = best, 0 = worst).
- Score = sum(weight x suitability) / sum(weight x 4) x 100.
- Dimensions without data for a place are left out for that place and listed; compare coverage before trusting a close ranking.
- Weights go from 0 (ignore) to 5 (very important). They are saved in this browser only.

It leaves out everything that is not in this data: cost of living, visas, healthcare, language, family, politics. The official advisories are shown next to it for that reason.

## How to read it


Example: If cold matters three times more than heat to you, set Cold to 3 and Heat stress to 1: the ranking changes instantly.

## Why it matters for Koh Samui

Different people weigh the same facts differently. The sliders make that explicit instead of hiding it in a single number.

## Sources

- [Open-Meteo -- historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
