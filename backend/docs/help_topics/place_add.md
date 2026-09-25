# Adding a place (search, server list, personal list)
id: place_add
short: Search a town by name (GeoNames via Open-Meteo), check its region and country, then add it. On a public site, only the admin can add to the shared list; anyone can keep a personal list in their own browser.
category: data
related: places_page, place_map
aliases: add place, geocoding, personal list

## What it is

- **Shared list (server)**: the place is collected like the others (forecast, air, warnings, advisories within a minute; climate normals, projections and river levels over the next days).
- **Personal list (this browser)**: stored in localStorage only. It shows the current conditions and 7-day forecast, the El Nino sensitivity and the country advisories, not the long-term matrix.

Always check the region shown in the search results: many towns share a name (there are three Gorokhovets in Russia). The default places were checked against OpenStreetMap as well.

## Sources

- [Open-Meteo -- geocoding API (GeoNames)](https://open-meteo.com/en/docs/geocoding-api)
- [OpenStreetMap Nominatim (geocoder)](https://nominatim.openstreetmap.org/)
