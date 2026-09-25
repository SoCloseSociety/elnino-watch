# Units and rounding

id: units_display
short: A machine unit code plus a readable label; numbers rounded to what the data supports.

## What it is
Every value has `unit` (a fixed code such as degC, mm, m, km/h, ug/m3) and `unit_label` (what is displayed: °C, mm, m, km/h, µg/m³). `value` is rounded for display and `value_raw` keeps the exact number the source sent; `value_label` is the full sentence-ready text ('0.5 m, forecast max on Thu 24 Sep').

## How to read it
Rounding: rain in whole mm, rain percentages whole, waves 0.1 m, gusts whole km/h, PM2.5 0.1 µg/m³, temperatures 0.1 °C, ENSO indices at the agency's own precision (RONI/ONI 0.01 °C, weekly Nino 3.4 0.1 °C). The source's value 0.46 m therefore shows as 0.5 m, with 0.46 kept in `value_raw`.

## Why it matters for Koh Samui
More decimals than the data supports suggest false precision; fewer can hide a threshold crossing. Thresholds are always compared with the raw value.

## Limits
Unit labels use Unicode (°, µ, ³). Old API clients that read only `unit` still get the code.

## Sources
- https://www.bipm.org/en/publications/si-brochure
