# The shopping budget card

id: shopping_budget
short: Indicative cost of the whole checklist for your household (adults, children, days), split by priority (Essential / Recommended / Useful) and by category, using the prices seen on the date shown.
category: prep
related: shopping_price_range, shopping_panel, preparedness

## What it is
API: GET /api/shopping/budget?adults=&children=&days=&include=. Each item's quantity is multiplied by the household and days (same rule as the checklist), priced from the Buy-panel listings (rounded up to whole packs) and added up by priority and category.

## How to read it
First number = cheapest combination, second = dearest. Items without a verified price are listed "to check", never counted as zero. A water tank (only if you have none) and baby / pet items (only if needed) are left out unless ticked. Big items (power station, generator, purifier) dominate the total; the Essential line is much smaller.

## Why it matters for Koh Samui
Seeing cost by priority helps decide what to buy first, and spreading purchases over the calm months avoids panic buying when a storm is announced.

## Limits
Delivery, installation and fuel not included; food uses stated per-day assumptions; prices older than 60 days are flagged "re-check".

## Sources
- https://www.ready.gov/kit
- https://www.makro.pro/en
