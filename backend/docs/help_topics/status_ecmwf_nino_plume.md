# ECMWF Nino 3.4 forecast plume

id: status_ecmwf_nino_plume
short: The European centre's monthly seasonal forecast of the Nino 3.4 temperature anomaly for the next 6 months, as a chart.

## What it is
Each month ECMWF runs its SEAS5 seasonal model 51 times with slightly different starting states. The plume chart shows every run's Nino 3.4 anomaly: thin red lines are the forecasts, the dashed line the observations. Two versions are kept: absolute and relative (RONI-like) index.

## How to read it
If most lines stay above +2 C, a very strong El Nino is forecast to continue; the spread of the lines is the uncertainty. Status key ecmwf_nino_plume {issued, label, images}.

## Why it matters for Koh Samui
A second opinion next to NOAA's and IRI's outlooks: when independent centres agree, confidence is higher about how long El Nino-type conditions will last over Samui.

## Limits
A picture, not numbers: we store the chart link only. Model forecasts made in spring are less reliable (spring barrier). Chart (c) ECMWF, CC-BY-4.0.

## Sources
- https://charts.ecmwf.int/products/seasonal_system5_nino_plumes
- https://charts.ecmwf.int/opencharts-api/v1/packages/opencharts/products/seasonal_system5_nino_plumes/axis/
