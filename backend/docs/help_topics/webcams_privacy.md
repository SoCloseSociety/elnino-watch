# Webcam privacy and ethics -- why only public, owner-published cams

id: webcams_privacy
short: Only cameras their owners publish for public viewing; never unsecured or private cameras.
applies_to: [all webcams]

## What it is
The rule this app follows for cameras: we only list cameras that their owner
deliberately publishes for anyone to watch -- a venue's own YouTube stream, a tourism
webcam portal, a hotel's page, a government agency (NOAA, JMA, the Bangkok city
traffic portal) or the Windy webcam directory where owners submit their own cams.

## How to read it
- **Never included**: "unsecured camera" directories (Insecam and similar), cameras
  found through device search engines (e.g. Shodan), default-password IP cameras, or
  anything reached by getting around a login or a block. Being reachable on the
  internet is not the same as being published.
- **Provider rules are followed**: if a provider forbids copying frames
  (SkylineWebcams) or locks its player to its own site, we only link to its page.
  Still images are shown directly only for open-licence sources (NOAA public domain,
  JMA open data licence), with credit.
- Our availability check is light (one small request per camera per 30-60 min) and
  identifies itself; we do not record or store any video.
- Street cams show public places and people passing by. Watch conditions, not people.

## Why it matters for Koh Samui
You get the "see it with your own eyes" check you need before a ferry or during
heavy rain, without taking part in anyone's loss of privacy.

## Limits
- We check a camera's public status when it is added (see backend/docs/WEBCAMS.md);
  if you spot a camera that looks private, tell us and it is removed.
- An owner can stop publishing any time; the cam then shows as offline.

## Sources
- SkylineWebcams terms of use: https://www.skylinewebcams.com/en/terms-of-use.html
- JMA website terms of use (open data licence): https://www.jma.go.jp/jma/en/copyright.html
- Windy Webcams API terms: https://api.windy.com/webcams/terms
