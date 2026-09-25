# Map event filters

id: filters_events
short: Show only some disaster types, sources or alert levels, a date range, a map box, or events within a distance of a point.

## What it is
Filters on the map events (cyclones, floods, droughts, fires, volcanoes, bleaching,
...): category, source (GDACS, NASA EONET, NASA FIRMS, Coral Reef Watch), severity
(green, orange, red, info), "updated since", a map rectangle, and "within N km of a
point" (default: the home radius, 800 km, around Koh Samui).

## How to read it
- Severity colours: GDACS green/orange/red are official alert levels (red = likely
  need for international help). For NASA FIRMS fires the colour is the number of
  satellite detections in 24 h (green < 25, orange >= 25, red >= 100), not an alert.
- "Within N km" results show the distance to the point.
- A rectangle that crosses the 180 degree line (Pacific) is handled.

## Why it matters for Koh Samui
The question for Koh Samui is "is anything dangerous close to us", which the
distance filter answers directly, while the rest of the map shows the El Nino
pattern worldwide.

## Limits
Positions are a single point per event (a cyclone's latest position, a fire
cluster's centre); a large flood or drought covers far more than its dot. Closed
events disappear on the next update; anything unseen for 30 days is deleted.

## Sources
- GDACS alert system: https://www.gdacs.org/Knowledge/overview.aspx
- NASA FIRMS active fires: https://firms.modaps.eosdis.nasa.gov/
