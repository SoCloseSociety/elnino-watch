# Live webcams -- see it with your own eyes

id: webcams
short: Public live cameras (beaches, piers, streets, buoys, satellites) to check conditions yourself; each shows whether it is live, stale or offline.
applies_to: [GET /api/webcams, status webcams, sources webcams_images / webcams_streams / webcams_windy]

## What it is
A curated list of public cameras: beach, pier and street streams on Koh Samui, the
ferry route (Koh Phangan, Koh Tao), wider Thailand, the El Nino "front line"
(Peru / Ecuador coast, Australia, Indonesia), NOAA buoy cameras in the open Pacific,
and satellite "space cams". Every camera is published by its owner for public
viewing (a venue's own YouTube channel, a webcam portal, a government agency).

## How to read it
- **Status badge** (checked every 30-60 min):
  - `live` -- a still image with a timestamp younger than the cam's limit (buoys 3 h,
    satellites 1 h). The age is shown next to it.
  - `online` -- the provider's own page says the stream is up (SkylineWebcams).
  - `reachable` -- the stream is still published and embeddable, but we cannot tell
    from outside whether it is broadcasting right now: the player will show it.
  - `stale` -- the newest image is older than the limit. Treat it as a photo of the
    past, not of now.
  - `offline` / `error` -- removed, marked offline by the provider, or the check
    failed. "Last OK" says when it last worked.
- **Mode**: `proxy` = still image we may show directly (NOAA, JMA); `embed` = the
  owner's own player (YouTube, Windy); `link` = open the official page (the provider
  does not allow reuse, e.g. SkylineWebcams).
- **Why** tells you what the camera is good for (e.g. "sea state toward Koh Phangan").

## Why it matters for Koh Samui
Forecasts and warnings tell you what is expected; a camera shows what is happening.
Before a ferry, a look at the north-coast and Big Buddha cams shows whether the
strait is white with breaking waves. In a flood or heavy-rain event the Chaweng and
Lamai street cams show standing water. Haze (from fires in El Nino dry seasons) shows
as a milky horizon.

## Limits
- A camera sees a few hundred metres to a few km. It is a spot check, not a forecast.
- Streams lag 5-60 s; still images lag 10-60 min (satellites) up to hours (buoys).
- At night most cams show little or nothing (beach cams go dark, true-colour satellite
  images are black, buoy cams stop). Use the infrared satellite image at night.
- Rain on the lens, sun glare and zoom make waves look smaller or bigger than they are.
- Venues move, rename or stop streams without notice; a `reachable` stream can still be
  an off-air placeholder. Official warnings (TMD, Marine Department) always win.
- No airport, Nathon pier or Donsak pier camera published by its owner was found;
  Windy webcams (needs a free key) may add some near Samui.

## Sources
- NOAA NDBC BuoyCAMs: https://www.ndbc.noaa.gov/buoycams.shtml
- JMA Himawari real-time images: https://www.data.jma.go.jp/mscweb/data/himawari/sat_img.php?area=se1
- Thai Meteorological Department (official warnings): https://www.tmd.go.th/en
