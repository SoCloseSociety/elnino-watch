# Space cams -- reading full-disk satellite images

id: webcams_space_cams
short: Newest Himawari and GOES satellite images: infrared works day and night, true colour only by day.
applies_to: [webcams kind satellite, ids himawari_*, goes18_*, goes19_*]

## What it is
The newest images from geostationary weather satellites 36,000 km above the equator:
- **Himawari-9 (Japan Meteorological Agency)** at 140.7 E: the full Earth disk and a
  Southeast Asia sector covering Thailand and the Gulf of Thailand. New image every
  10 minutes.
- **GOES-West (GOES-18)** over the central / eastern Pacific, where the Nino 3.4
  region lies, and **GOES-East (GOES-19)** over the Americas (Peru / Ecuador).

## How to read it
- **Infrared (Himawari B13, GOES band 13)**: brightness = cold. Bright white blobs are
  tall, cold thunderstorm tops (heavy rain); grey is low cloud; dark is clear sky or
  warm sea. Works day and night.
- **True colour (Himawari "True Color Reproduction")**: what your eye would see;
  cloud is white, haze and smoke are milky brown-grey. Black at night.
- **GeoColor (GOES)**: true colour in daylight, infrared clouds plus city lights at
  night.
- A spiral of bright white cloud with a clear centre is a tropical cyclone.
- The time shown is UTC (Koh Samui = UTC + 7).

## Why it matters for Koh Samui
El Nino moves the Pacific's big thunderstorm clusters east, away from Indonesia and
toward the central Pacific: fewer bright white clusters over the Maritime Continent,
more near the date line. On the Southeast Asia sector you can watch storms and squall
lines approach the Gulf of Thailand and smoke haze in dry spells.

## Limits
- Pixels are 2-4 km: a single storm cell over Samui is a dot.
- Bright cloud does not always rain; thin high cirrus looks bright in infrared too.
- The image is 10-40 min old when you see it (scan + publish + our check interval).
- For rain now, use the radar layer; for forecasts, the local risk page.

## Sources
- JMA Himawari real-time images: https://www.data.jma.go.jp/mscweb/data/himawari/sat_img.php?area=se1
- JMA: Himawari imager bands: https://www.data.jma.go.jp/mscweb/en/himawari89/space_segment/spsg_ahi.html
- NOAA NESDIS STAR GOES imagery: https://www.star.nesdis.noaa.gov/GOES/index.php
