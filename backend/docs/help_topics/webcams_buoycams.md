# NOAA BuoyCAMs -- cameras on buoys in the open Pacific

id: webcams_buoycams
short: NOAA cameras on weather buoys in the open Pacific; daylight photos about once an hour.
applies_to: [webcams kind buoy, ids ndbc_*]

## What it is
Cameras mounted on NOAA National Data Buoy Center weather buoys. Each image is a
strip of 6 photos taken at the same time in different directions from the buoy,
hundreds of km from land (Hawaii, US west coast, Gulf of Alaska, Bering Sea). NOAA
publishes them as US public-domain data, so we can show the image itself.

## How to read it
- The time in the file name is UTC; "age" tells you how old the photo is.
- Whitecaps and foam = strong wind; long smooth swell lines = distant storms.
- Photos are taken about once an hour in daylight only. At night (buoy local time)
  the newest photo is from the evening before and is marked `stale`.
- `offline` = NOAA currently lists no photo for that buoy (camera fault or maintenance).

## Why it matters for Koh Samui
They show the real Pacific the El Nino data comes from. The Hawaii buoys (51000-
51004, 51101) sit in the subtropical Pacific; during El Nino the central Pacific
warms and storms shift east, which changes what these cameras see. They are context,
not a Koh Samui signal.

## Limits
- There are no BuoyCAMs on the equatorial TAO array or in the Gulf of Thailand.
- A single photo per hour in daylight; salt on the lens, tilt from waves.
- For numbers (sea temperature, wind, waves) use the buoy data on the Ocean page.

## Sources
- NOAA NDBC BuoyCAM map: https://www.ndbc.noaa.gov/buoycams.shtml
- Station pages (data behind each cam): https://www.ndbc.noaa.gov/station_page.php?station=51002
