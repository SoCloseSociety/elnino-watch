# Satellite sea level anomaly (NOAA CoastWatch)

id: source_noaa_sla_regions
short: Daily sea surface height from radar satellites, averaged over key Pacific boxes, the Gulf of Thailand and the sea around Samui.

## What it is
Radar altimeters (Sentinel-6, Jason-3, SWOT, Sentinel-3, CryoSat-2) measure the height of the sea surface to a few centimetres. NOAA CoastWatch merges them into a daily 0.25 deg map. Twice a day the app averages the last 15 days over 6 boxes.

## How to read it
Values are cm above the DTU15 mean sea surface (a 1993-2012 reference), so they include roughly 8-10 cm of long-term sea level rise. On 2026-09-22 the Nino 3.4 box was +37 cm and the western Pacific -8 cm.

## Why it matters for Koh Samui
El Nino is a sloshing of the Pacific: warm water piles up in the east (sea level up) and drains from the west (sea level down) weeks before surface temperatures peak. Around Samui, higher sea level adds to storm-surge and high-tide flooding risk.

## Limits
Coastal boxes (Samui, Gulf) are less accurate because altimeters struggle near land. The server is sometimes slow or down; the source then shows an error, never old numbers as new.

## Sources
- https://coastwatch.noaa.gov/cw_html/SSH_SeaLevelAnomaly.html
- https://coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDsshDaily.html
