# Storm tracks on the map

id: event_category_cyclone_track
short: Lines on the map for tropical cyclones: past track and forecast positions from JMA and JTWC.

## What it is
For JMA and JTWC storms the map item has a line (GeoJSON LineString, [lon, lat]) joining the past track and the forecast positions, and a point at the current position. The payload lists each forecast point with time, winds and distance to Samui.

## How to read it
Colour = severity by distance: red within 300 km of Samui, orange within 800 km, green further away. The same storm can appear twice (JMA and JTWC) with slightly different positions and winds.

## Why it matters for Koh Samui
A storm's closest forecast approach is what decides whether the sea around Samui will close; watch storms whose line points toward the Gulf of Thailand.

## Limits
Forecast points beyond 72 h are uncertain by several hundred km.

## Sources
- https://www.jma.go.jp/bosai/map.html#contents=typhoon&lang=en
- https://www.metoc.navy.mil/jtwc/jtwc.html
