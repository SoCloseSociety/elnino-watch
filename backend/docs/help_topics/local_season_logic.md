# Season-aware risk rules

id: local_season_logic
short: Some thresholds weigh differently depending on Samui's season.

## What it is
Samui's rain year: northeast monsoon October-January (November wettest, about half of the year's rain October-December); dry season February-May (February driest); southwest monsoon June-September, when the island is sheltered.

## How to read it
Water: in the dry season the 180-day rain window (which holds the last monsoon refill) is used if it is worse than the 90-day one; in October-December a rain deficit during a strong El Nino is at least 'Prepare', because the reservoirs refill only then; a rain-only 'Act' needs at least 100 mm really missing, not just a low percentage of a tiny dry-season normal. Flood: heavy rain forecast on ground soaked by 150 mm or more over the past 7 days raises the flood level by one; 250 mm in a week alone is 'Watch'. Sea: TMD wave warnings for the Andaman Sea only are ignored (they do not concern the Gulf).

## Why it matters for Koh Samui
El Nino makes the February-April 2027 dry season the water danger window, while floods still come with the northeast monsoon (for example the November-December 2024 floods in the South and the 2011 and 2017 floods).

## Limits
Normals come from ERA5 (about 30 km cells), which underestimates rain at Samui's stations; comparisons are ERA5 against ERA5, so the bias largely cancels. The 7-day antecedent rain uses model analyses, not gauges.

## Sources
- https://open-meteo.com/en/docs/historical-weather-api
- https://open-meteo.com/en/docs
- https://www.tmd.go.th/en/warning-and-events/warning-storm
