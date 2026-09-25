# El Nino analogs: what past strong events did to Samui

id: analogs
short: The strong El Ninos since 1950 (1982-83, 1991-92, 1997-98, 2009-10, 2015-16, 2023-24, plus 1987-88) replayed for Koh Samui: rain of the monsoon and the dry season, heat and dry spells from ERA5, next to what actually happened (rationing, floods, bleaching), with neutral years as the yardstick.
category: samui
related: analogs_limits, analogs_reading, place_enso, local_season_logic, series_era5_global_t2m
aliases: past El Ninos, historical analogs, what happened last time, 1997, 2015-16, 2023-24

## What it is

An "analog" is a past year that looked like this one. The page (GET /api/local/analogs) takes every strong or very strong El Nino in NOAA's record since 1950 and shows, for each, the island's "water year" around the event: July of the year the event grew (2026 for the current one) to June of the next, when its dry season ends.

Two kinds of information sit side by side, and the page labels them:

- **Reanalysis** (kind "reanalysis"): numbers from ERA5, the European reconstruction of past weather, for the ~30 km grid cell that holds Maenam, at sea level (the same cell and correction as the live rain-deficit factor). For each event: rain of the Oct-Dec refill (the NE monsoon), of the Jan-May dry season and of the Feb-Apr danger window, each as a percentage of the 1991-2020 average of the same cell; the highest feels-like temperature of the dry season and the number of days at or above 39 °C feels-like; the longest run of days under 1 mm of rain.
- **Documented** (kind "documented"): dated reports of what happened on Samui, Koh Phangan, Koh Tao and the southern provinces: water rationing on Samui in September-October 2016 and in 2023-24, the October 2015 haze that turned flights back, the coral bleaching of 1998, 2010, 2016 and 2024, and the floods of the NE monsoon. Every one links to the page it comes from, with the sentence quoted; the page was checked live on the date shown.

The peak ONI and RONI of each event are read from the NOAA CPC series the app already collects (never typed in). The current 2026-27 event is shown the same way, with its indices so far and its Jun-Sep rain so far.

## How to read it

Columns of the event table: Event | Peak ONI / RONI | Oct-Dec rain % | Jan-May rain % | Feb-Apr rain % | Max feels-like | Days >= 39 °C | Longest dry spell | Impacts

- Rain percentages: 100 = the 1991-2020 average of the ERA5 cell; 60 = only six tenths of the usual rain. Under 75% is what the live water factor calls "watch", under 60% "prepare".
- Heat: ERA5 cell values run a degree or two below a thermometer on the island; compare events with each other and with the neutral-year median, not with the forecast page.
- Longest dry spell: consecutive days with less than 1 mm, Jan-May.
- **Neutral baseline**: the median of the same numbers over the years whose ONI stayed between -0.5 and +0.5 °C from SON to FMA (neither El Nino nor La Nina); the count of years is shown.
- **Takeaways**: sentences generated from the numbers above and nothing else, e.g. how many of the events had a Feb-Apr rain under 60% of normal.
- The 1987-88 event is listed in older tables as strong; in the current CPC ONI it peaks at +1.49 °C, just under the +1.5 °C band, and the page says so.

## Why it matters for Koh Samui

The live factors say what is happening now; the analogs say what the same kind of El Nino did before, on this island, in numbers and in newspaper reports. They are the best available answer to "how bad can the 2027 dry season get", and they show that the NE monsoon can still flood the island in an El Nino winter (January 2016).

## Limits

See "Analogs: limits". In short: a 6-7 event sample, one 30 km grid cell, a warming climate since 1982, and no two El Ninos alike.

## Sources

- [Open-Meteo historical weather API (ERA5)](https://open-meteo.com/en/docs/historical-weather-api)
- [NOAA CPC ONI table (cold and warm episodes by season)](https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php)
- [Bangkok Post, 10 Oct 2016: Severe water shortage on Koh Samui](https://www.bangkokpost.com/thailand/general/1107052/severe-water-shortage-on-koh-samui)
