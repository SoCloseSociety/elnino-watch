# Water / drought (aridity)
id: place_water
short: Yearly rain compared with how much water the air could evaporate (P/ET0, the UNEP aridity index), plus a penalty for long dry seasons.
category: hazards
related: place_levels, place_enso, era5
aliases: drought, aridity, water supply, P/ET0

## What it is

ET0 is the reference evapotranspiration: how much water a well-watered grass would lose to the air. Rain divided by ET0 is the aridity index used by UNEP and the JRC World Atlas of Desertification.

A place can be humid over the year and still run dry for months: the score gets +1 if 3 or more consecutive months receive less than half of their evaporation. Local context (for example Samui's small island reservoirs and the 2026 rationing) is added to the note, with its source, but does not change the score.

## How to read it

Columns: Aridity index P/ET0 | Class | Exposure

- >= 0.65 | humid | 0
- 0.5-0.65 | dry sub-humid | 1
- 0.2-0.5 | semi-arid | 2
- 0.05-0.2 | arid | 3
- < 0.05 | hyper-arid | 4

+1 (max 4) for 3+ consecutive months with rain below half of ET0. Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.

## The current "Water" factor (place level): climate profiles

The current factor compares recent ERA5 rain with the place's own 1991-2020 ERA5 normal for the same calendar days. How long a window counts depends on where the water comes from, so each place gets a profile from its normals:

- **Tropical** (coldest month >= 18 C, Koppen A), e.g. Maenam / Koh Samui: supply leans on surface stores that a dry quarter drains. 90 days: < 75% Watch, < 60% Prepare, < 40% and >= 100 mm short Act (the Koh Samui watch bands).
- **Temperate humid, groundwater-buffered** (coldest month < 18 C and P/ET0 >= 0.5), e.g. Saint-Gatien-des-Bois (Normandy) and Gorokhovets: soil and aquifers refill each winter and carry supply through a dry quarter, so long windows count most.

Columns: Window | Watch | Prepare | Act

- 365 days | < 85% | < 75% | < 65%
- 180 days | < 75% | < 60% | < 50%
- 90 days | < 60% | < 35% | never on its own

A shorter window can sit at most one level above the longest window available, and 90 days alone can raise at most Watch (at most Prepare when no longer window can be computed). Act also needs >= 100 mm actually missing. The explanation lists every window, its level and which one set the level.

- **Dry climate** (P/ET0 < 0.5): no bands tuned for dry climates yet, the 90-day Koh Samui bands are used and the explanation says so.

Limits: the collector stores the last 120 days of ERA5, so today the 180- and 365-day windows cannot be computed and the temperate level rests on 90 days only; the explanation says so and calls the level provisional. Longer windows are never estimated. The bands approximate the WMO SPI categories (-1, -1.5, -2) for typical rain variability; they are not fitted per place, because the stored normals keep only monthly means.

## Why it matters for Koh Samui

Water security is where El Nino hits Samui hardest. The current rain deficit is the "Water" factor of the place level.

## Sources

- [JRC World Atlas of Desertification -- aridity](https://wad.jrc.ec.europa.eu/patternsaridity)
- [WMO -- Standardized Precipitation Index User Guide (WMO-No. 1090)](https://library.wmo.int/idurl/4/39629)
- [Bangkok Post, 29/07/2026 -- Koh Samui faces water rationing](https://www.bangkokpost.com/thailand/general/3293479/koh-samui-faces-water-rationing)
