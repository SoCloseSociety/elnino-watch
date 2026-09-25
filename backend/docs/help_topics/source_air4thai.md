# Measured air quality (Air4Thai)

id: source_air4thai
short: Hourly PM2.5, PM10 and Thai AQI measured at government stations in southern Thailand.

## What it is
The Pollution Control Department's Air4Thai network. The app keeps the stations within 300 km of Samui; the nearest is Surat Thani (about 87 km). Koh Samui itself has no station. Series air4thai_<station>_pm25 and _pm10 (ug/m3) and _aqi; status key air4thai_samui = nearest station.

## How to read it
Thai AQI bands: 0-25 very good (blue), 26-50 good (green), 51-100 moderate (yellow), 101-200 starting to affect health (orange), above 200 affects health (red). PM2.5 above 37.5 ug/m3 (24-hour) is above Thailand's standard. A missing value means the station does not measure that pollutant.

## Why it matters for Koh Samui
El Nino dry seasons bring more fires in Sumatra, Borneo and mainland South-East Asia and so more haze. These are real measurements, a check on the model forecast (CAMS) used for Samui.

## Limits
The nearest station is on the mainland; Samui's air is usually cleaner thanks to sea breezes. A station can stop reporting for hours; its timestamp is shown.

## Sources
- https://air4thai.pcd.go.th/webV3/
- https://air4thai.pcd.go.th/services/getNewAQI_JSON.php
