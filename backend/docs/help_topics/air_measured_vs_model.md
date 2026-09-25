# Air quality: measured station and CAMS model

id: air_measured_vs_model
short: PM2.5 from the nearest Thai government station (measured) and from the CAMS model at Samui.

## What it is
Two sources: the Pollution Control Department's Air4Thai ground stations (measured; the nearest is Surat Thani, about 87 km away on the mainland, because Koh Samui has no station) and Copernicus CAMS via Open-Meteo (a model at Samui's point: past 24 h mean = model analysis, next 72 h = forecast).

## How to read it
The level uses the worst of the three: measured PM2.5, CAMS 24 h mean, worst CAMS forecast 24 h mean. Thresholds (PCD 24 h bands): above 37.5 µg/m³ Watch, above 75 Prepare, above 125 Act. The shown value is the one that sets the level; a measured value wins a tie. A station reading older than 6 h is not used.

## Why it matters for Koh Samui
El Nino years bring haze from fires in Indonesia and Malaysia (2015, 2019). A mainland station sees regional haze a few hours before or after the island.

## Limits
Surat Thani city air includes local traffic and burning; CAMS is coarse (about 40 km). Neither is a measurement on the island.

## Sources
- https://air4thai.pcd.go.th/webV3/
- https://open-meteo.com/en/docs/air-quality-api
