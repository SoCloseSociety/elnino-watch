# Shopping panel (Preparedness page): where to buy, prices, budget

Owner need: for every checklist item that can be bought, know where to buy it (Lazada,
Shopee, Thai retailers, shops on Koh Samui), what it costs, and what spec to look for,
plus a budget for the household. Built 2026-09-24.

## Data policy (read before editing)
- **No runtime scraping.** Lazada / Shopee forbid it (terms + anti-bot); the app only
  serves the curated file `app/shopping/catalog.py`. Search links are plain URLs the
  user opens in a browser.
- **Every price was seen on a page**, on `CHECKED_AT`, and the page URL is stored with it:
  - Makro (makro.pro), HomePro (homepro.co.th), Global House (globalhouse.co.th):
    retailers' own pages, price as displayed that day (promotions included).
  - Priceza (priceza.com), a Thai price-comparison site: used only where these
    retailers had no listing (Sawyer filters, dry bags, crank radios, whistles, 3M
    9501 masks, one DEET spray). Those listings are marked `source: "marketplace"`.
- **No price found = no price.** `listings: []` + `price_note` ("check link"). Currently:
  water purification tablets, pharmacy ORS, second SIM card. Baby formula and pet food
  have reference pack prices but are not budgeted (days per pack depends on the child /
  animal). Fuel for the fuel can is not priced (links to PTT's price page).
- **Freshness**: prices older than `STALE_AFTER_DAYS` (60) are flagged `recheck` per
  listing and item, and the budget carries `recheck: true`.
- **Physical stores** are listed only when a page confirms they exist (`source`): Makro
  Koh Samui (Bophut, makro.co.th), Global House Samui (Maenam), HomePro Samui (Bophut),
  Big C Supercenter Samui (Bophut), Lotus's (several branches), Boots Central Samui
  (Chaweng). Links are Google Maps *searches*, no invented coordinates. Stock is not known.
- Boots' own online search could not be linked (its search URLs return 404/redirect to
  the home page on 2026-09-24): Boots appears as a physical store only.

## Model
`catalog.ITEMS`: one entry per preparedness item id (test enforces full coverage).
Buyable entries: `q_en` / `q_th` (search keywords), `shops` (RETAILERS keys), `local`
(STORES keys), `spec` + `why`, `listings` [{retailer, title, price, units, url, source}],
optional `components` (kits: power station + panel, fuel can, hygiene set), `assumption`,
`budget` (`default` | `conditional` baby/pets | `optional` water tank), `price_note`.
`units` = how many checklist units (the item's `unit`) one listing covers, e.g. 6 for a
6 L bottle of water, 10/3 person-days for 10 cans under the "3 cans per person per day"
assumption; `None` = not convertible (not budgeted).

## Budget maths (`offers.budget`)
needed = qty x multiplier(per) with the Preparedness page's rule (person/day -> persons x
days, person -> persons, household -> 1; children count as persons). Per listing: packs =
ceil(needed / units), cost = packs x price; item range = cheapest..dearest listing. Kits
sum each component's cheapest..dearest. Unpriced items are listed (`unpriced`), never 0.
Totals per priority (must/should/nice) and per category; `label` = "Indicative, prices
checked on <date>". Delivery, installation and fuel are excluded.

2 adults x 14 days, prices of 2026-09-24 (default modes): Essential 6,898-20,330 THB,
Recommended 19,818-35,073 THB, Useful 11,304-29,856 THB, total 38,020-85,259 THB
(+ water tank, baby and pet items: 42,009-103,648 THB).

## API
- `GET /api/shopping` -> {checked_at, age_days, stale_after_days, recheck, note, method,
  retailers, stores, references, coverage {prep_items, covered, missing, unknown},
  items: {item_id: {id, label, unit, priority, category, buyable, price_status
  (ok|recheck|unverified|not_buyable), checked_at, reason? | spec, why, assumption,
  price_note, budget_mode, unit_price {min,max,unit}, listings [...], components [...],
  search_links [{retailer, name, kind, lang, query, url, hint}], local_stores [...]}}}
- `GET /api/shopping/budget?adults=1..20&children=0..20&days=1..120&include=conditional&include=optional`
  -> {household, currency, checked_at, age_days, recheck, label, included_modes, total
  {min,max}, by_priority {must|should|nice: {min,max,priced,unpriced[]}}, by_category
  [...], items [{id,label,category,priority,needed,unit,cost_min,cost_max,price_status,
  note}], excluded, not_buyable, missing_from_catalog, caveats}
- `GET /api/shopping/{item_id}` -> one item (404 if unknown).

## Maintenance
1. Links: `cd backend && uv run python -m app.shopping.check_links` (hits the network on
   purpose; 391 links, all 200 on 2026-09-24).
2. Prices (manual, every <= 60 days): open each listing URL, update `price` (and title if
   the product changed), replace dead products with a current one from the same retailer,
   then bump `CHECKED_AT`. Never type a price you did not see.
3. New preparedness item: `tests/test_shopping.py::test_every_preparedness_item_has_a_shopping_entry`
   fails and names the id: add a buyable entry or `_no(id, reason)`.
4. Help topics: `docs/help_topics/shopping_*.md` and `frontend/src/help/topics/shopping.ts`
   (frontend text wins on the same id).
