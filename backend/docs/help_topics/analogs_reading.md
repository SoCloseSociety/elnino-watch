# Analogs: the numbers behind each event

id: analogs_reading
short: How each analog number is computed from ERA5 daily data (water year, seasons, percentages of the 1991-2020 normal, heat days, dry spells) and how the neutral baseline and the takeaways are built.
category: samui
related: analogs, analogs_limits, local_season_logic, valid_for, value_kind
aliases: water year, dry spell, heat days, neutral years, analog method

## What it is

The recipe of GET /api/local/analogs, so every number can be checked.

- **Data.** Open-Meteo archive, model ERA5, point 9.5705 N 99.9957 E at 10 m (the archive snaps it to its 9.5 N 100.0 E cell), daily rain, maximum air temperature and maximum feels-like temperature from 1950. Fetched once in decade windows (one per hour after start-up) and kept as monthly totals and counts in status `samui_era5_history`; the current year is refreshed once a day. Monthly rain and maxima are also series (`samui_era5_month_precip`, `samui_era5_month_temp_max`, `samui_era5_month_apparent_max`, dated the 15th) for charts.
- **Water year.** July of the year the El Nino grows (y) to June of the next (y+1): 1997-98 = July 1997 to June 1998. Seasons: Jun-Sep y (SW monsoon, "so far" for the current event), Oct-Dec y (NE monsoon refill), Jan-May y+1 (dry season), Feb-Apr y+1 (danger window). A season counts only when every month has at least 25 valid days.
- **Percent of normal.** The season total divided by the sum of the 1991-2020 monthly means of the same months (same cell, same reanalysis).
- **Heat.** Max feels-like = the highest daily maximum apparent temperature of Jan-May, with its date; days >= 39 °C feels-like is a count over Jan-May (the monthly table also keeps a count of days >= 35 °C air temperature, which is 0 in every year at this sea-level cell and is not shown). The normal is the 1991-2020 mean of the same count.
- **Longest dry spell.** The longest run of consecutive days with less than 1 mm of rain within Jan-May (and, separately, within Oct-Dec). Runs are followed across month ends.
- **Peak ONI / RONI.** The highest 3-month value between MAM of year y and MJJ of year y+1 in the NOAA CPC series stored by the app (`oni`, `roni`); "JJA" values are the same season as the current event's latest ONI, for a like-for-like comparison of the stage the event had reached.
- **Neutral baseline.** Years whose ONI stayed within +-0.5 °C from SON(y) to FMA(y+1); for each metric the median, mean, min and max over those years and the count.
- **Takeaways.** Sentences assembled from these numbers only (counts of events under a threshold, medians, the highest value and its year). No sentence contains a number that is not in the payload.

## How to read it

Every number carries `kind` (reanalysis for ERA5, observed for the indices, documented for reports) and the months it covers; "complete: false" means a month is missing (the history is still being fetched) and the number is null, never estimated.

## Why it matters for Koh Samui

A reader can rebuild any figure from the same public data, which is the point of the whole tracker.

## Sources

- [Open-Meteo historical weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [NOAA CPC ONI](https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt)
- [NOAA CPC RONI](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/)
