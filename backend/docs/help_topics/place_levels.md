# Place level (current, 0-4)
id: place_levels
short: One level per place for NOW and the next 7 days, from 9 factors (heat, cold, water, flood, storm, air, wildfire, earthquakes, official warnings). Same names as the Samui watch: Normal, Watch, Prepare, Act, Leave.
category: hazards
related: place_current, place_warnings, risk_levels, data_coverage, heat_index, pm25
aliases: place level, current level, factors

## What it is

Each factor is scored 0-4 from real data and shows its value, threshold, source and date. The overall level is:

- **R1**: the highest factor, each capped (earthquakes at 2 Prepare; cold, water, flood, air, wildfire and warnings at 3; heat and storm can reach 4).
- **R3**: two physical hazards at 2 Prepare or more at the same time give at least 3 Act.
- If heat, water, flood or storm has no current data, the level is **Unknown**, never Normal.

For Maenam the detailed Koh Samui watch (with water supply, sea state, ferries...) remains the reference; its level is shown on the Maenam card.

## How to read it

Columns: Factor | Watch (1) | Prepare (2) | Act (3)

- Heat: highest feels-like, 7 days | >= 39 C | >= 41 C (1-2 days) | >= 41 C on 3+ days (>= 54 C: Leave)
- Cold: lowest feels-like, 7 days | <= -10 C | <= -28 C | <= -40 C (<= -48 C: Leave)
- Water: ERA5 rain, 90 days, % of normal | < 75% | < 60% | < 40% and >= 100 mm short
- Flood: forecast rain / river | > 35 mm in 24 h, or river above its 99th percentile | > 90 mm/24 h or 150 mm/72 h, or a 2-year river flood | >= 150 mm/24 h or 250 mm/72 h, or a 10-year river flood
- Storm: forecast gusts / cyclones | >= 75 km/h, or a cyclone within 800 km | >= 89 km/h | >= 118 km/h, or orange/red cyclone within 500 km (300 km: Leave)
- Air: PM2.5 24 h mean | > 37.5 | > 75 | > 125 ug/m3
- Wildfire: VIIRS detections | >= 3 within 100 km | >= 25 within 50 km | >= 100 within 50 km
- Earthquakes, 30 days, 300 km | M5+ within 150 km | M6+ (aftershocks possible) | M7+ (capped at 2 overall)
- Official warnings | yellow / region named | orange / severe wording | red

Critical factors: heat, water, flood, storm. A factor whose data is too old cannot say Normal: it becomes unknown.

## Why it matters for Koh Samui

The current level tells you how each place is doing today. It is not a verdict on the place: a Russian winter cold snap or a Thai dry spell are normal parts of those climates. Use the matrix for the long view.

## Sources

- [US National Weather Service -- Heat index](https://www.weather.gov/ama/heatindex)
- [US National Weather Service -- Wind chill chart](https://www.weather.gov/safety/cold-wind-chill-chart)
- [Air4Thai (Thai Pollution Control Department)](https://air4thai.pcd.go.th/)
