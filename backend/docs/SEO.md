# SEO and natural referencing

Goal: anyone searching for the 2026-27 El Nino, for ENSO numbers, or for its impact on
Thailand and Koh Samui should find this tracker. This document is the map of what the
app does for that, what the owner still has to do by hand (Search Console, DNS), and
the keyword plan. Technical entry points: `backend/app/seo.py` (server side),
`frontend/src/seo/` (client hook), `frontend/scripts/prerender.mjs` (content export),
`backend/tests/test_seo.py`.

## 1. How the SPA becomes crawlable

The React app is served by FastAPI. `app/seo.py` registers, BEFORE the SPA catch-all,
one GET route per page (`/`, `/map`, `/indices`, `/news`, `/samui`, `/history`, `/prep`,
`/places`, `/cams`, `/learn`, `/sources`) plus `/learn/<topic_id>` for each of the 243 Learn topics.
Each answers `frontend/dist/index.html` with:

- `<head>`: the route's `<title>` (<= 60 chars) and description (140-160 chars),
  `<link rel=canonical>`, `hreflang` (`en` + `x-default`), Open Graph and Twitter card
  tags pointing at the live card `/og/current.png`, `robots` (`index,follow,
  max-image-preview:large`; `noindex` + HTTP 404 for an unknown topic id, so no soft 404),
  the Search Console / Bing verification metas when set, a JSON-LD `@graph`, and a
  small JSON route map (`<script id="seo-routes">`) the frontend hook reads.
- `<div id="root">`: a server-rendered summary (`#prerender`) of the live data for that
  route: ONI and RONI with their season, the weekly Nino 3.4 anomaly with its week,
  NOAA CPC status with issue date, IRI probabilities, the Koh Samui level with its
  evaluation time, then route-specific content (index table, Samui factors / actions /
  triggers, latest bulletins, red/orange events, preparedness categories and emergency
  numbers, the source table, the whole glossary with links to every `/learn/<id>`, the
  FAQ text, the myths; for `/history` the analog takeaways, the seven-events table with
  the neutral median and the "2026-27 so far" row, every documented impact with its link,
  the "looked for, not found" list and the method, all from `analogs.build()`). Every
  value comes from the SQLite tables; missing data is written as "no data yet" / "n/a",
  never estimated. React's `createRoot().render()` clears the
  container on mount, so people see the app and crawlers see the summary. A `<noscript>`
  note says the charts need JavaScript.
- CSP: the two injected `<script>` blocks are sha256-hashed into `script-src` for that
  response (`seo.csp_with`), next to the hashes `security.py` computes for the built
  index.html. `'unsafe-inline'` is never added. JSON data blocks are not executed by
  browsers, but declaring them keeps the console at zero violations.

`GET /sitemap.xml` lists the 11 pages and every topic URL; `lastmod` is the date of the
last REAL change of that page's data (status updates, newest feed item, newest index
fetch, the Learn export date), and a page with no data yet has no `lastmod` at all.
`GET /robots.txt` allows everything a person can open and disallows `/api/` except the
six JSON endpoints referenced as Dataset distributions (`/api/latest`, `/api/series`,
`/api/status`, `/api/local`, `/api/local/weather`, `/api/sources`): they are cheap, cached
and documented; the rest of `/api/` is parameterised JSON that would only burn crawl
budget. `/docs`, `/redoc`, `/openapi.json` are disallowed (404 in public mode anyway).

Legacy French paths (`/carte`, `/actualites`, `/preparation`) and trailing-slash
variants answer HTTP 301 to the canonical path.

### One origin setting

`settings.public_origin` (env `PUBLIC_ORIGIN`, default `https://elnino.soclose.co`)
is the only place the canonical origin lives: canonical links, sitemap, OG URLs, JSON-LD
ids, robots and the IndexNow host all derive from it. Moving to `elnino.soclose.co` is
`PUBLIC_ORIGIN=https://elnino.soclose.co` in `/opt/elnino/.env` and a restart.

### Learn content export (`npm run seo:build`)

`frontend/scripts/prerender.mjs` bundles `src/help/content.ts` with esbuild (already a
Vite dependency) and writes `frontend/public/seo/{topics,faq,myths}.json` (plain text,
markdown-lite stripped, `[[links]]` resolved to titles). It runs inside `npm run build`
and fails the build if `validateTopics()` reports a broken link or an em dash. Vite copies
`public/` into `dist/`; the backend reads `dist/seo/` first, then `public/seo/`.

### Client side (`frontend/src/seo/useSeo.ts`)

`useSeo()` keeps the tags right on in-app navigation (tab title, share sheet). It reads
the embedded route map so titles have one source of truth (`ROUTES` in `seo.py`).
Integration lines are in section 7.

## 2. Structured data (JSON-LD, every page)

`@graph` with `Organization` (SoClose), `WebSite`, `WebPage` (`dateModified` = last
successful fetch), `BreadcrumbList`, then per route:

- `/` and `/indices`: four `Dataset` nodes (ONI+RONI, weekly Nino 3.4, SOI CPC+BoM,
  MEI.v2) with `temporalCoverage` (first/last row in the DB), `spatialCoverage`
  (GeoShape box of the index region), `variableMeasured` (latest value + date),
  `distribution` (`DataDownload` -> `/api/series?...` JSON and `/api/latest`),
  `isBasedOn` (the NOAA / BoM pages), `license` + `conditionsOfAccess` (the license note
  below), `dateModified`.
- `/` and `/samui`: the Koh Samui weather `Dataset` (Open-Meteo, GeoCoordinates of
  Maenam) and a `Place` node.
- `/learn`: `FAQPage` with the 18 FAQ entries (plain-text answers).
- `/learn/<id>`: `TechArticle` (headline, section, citations = the topic's sources,
  `dateModified` = export date).

License notes per source (also in `DATASETS[*]["license_note"]`):

| Source | Note |
|---|---|
| NOAA CPC (ONI, RONI, weekly Nino, SOI), NOAA PSL (MEI) | US Government work, public domain; cite the agency. |
| Australian BoM (SOI Troup, outlook) | Commonwealth of Australia copyright notice, attribution required (bom.gov.au/other/copyright.shtml). |
| Open-Meteo (Samui weather, marine, air) | CC BY 4.0, attribution required (open-meteo.com/en/terms). |
| IRI plume, TMD, GDACS, NASA GIBS, Copernicus | Quoted with a link and issue date; not redistributed as datasets. |

No `SearchAction` is declared: the glossary search is client state only. If the Learn
page starts reading `?q=`, add `potentialAction: {"@type": "SearchAction", "target":
"<origin>/learn?q={q}", "query-input": "required name=q"}` to `_website()` in `seo.py`.

## 3. Open Graph card, icons, manifest

- `GET /og/current.png`: 1200x630 drawn with Pillow (no system fonts, ASCII-folded
  text, ~1 MB RAM): ONI / RONI / Nino 3.4 tiles with their periods, the NOAA CPC status
  with issue date, the Koh Samui level, "Data as of ...". Cached 1 h in memory, keyed on
  the newest successful fetch, `ETag` + `Cache-Control: public, max-age=3600`.
  `frontend/public/og-default.png` is the same card without numbers, used only if
  Pillow is missing.
- Icons: `favicon.svg` (master), `icon-16/32/192/512.png`, `apple-touch-icon.png`
  (180), `icon-maskable-512.png` (80 % safe zone), generated from the SVG with
  macOS `qlmanage` + `sips` + Pillow. `site.webmanifest` (standalone, theme `#07111f`).

## 4. Keyword plan (what each page should rank for)

| Query family | Page | Why it fits |
|---|---|---|
| el nino 2026, el nino 2027, el nino 2026-27, super el nino 2026, el nino tracker, enso live, el nino today | `/` | live numbers in the summary, Dataset markup, hourly `lastmod` |
| nino 3.4 today, nino 3.4 anomaly, oni index, roni, relative oceanic nino index, soi today, mei index, enso indices | `/indices` and `/learn/oni`, `/learn/roni`, `/learn/nino34`, `/learn/soi`, `/learn/mei_v2` | table of latest values with periods; one explainer URL per index |
| el nino thailand, el nino koh samui, koh samui weather el nino, koh samui drought, samui water shortage 2027, el nino drought thailand 2027 | `/samui`, `/learn/el_nino_thailand`, `/learn/samui_seasons`, `/learn/samui_water_supply` | factor table with sources, Place markup, FAQ "Does El Nino mean no rain on Samui?" |
| el nino preparedness, prepare for el nino, drought checklist thailand, koh samui emergency numbers | `/prep` | categories + emergency numbers in the summary |
| el nino forecast, enso forecast 2027, iri enso probabilities, noaa el nino advisory, la nina 2027 | `/`, `/news`, `/learn/iri_plume`, `/learn/cpc_alert_system` | IRI table + CPC status with issue dates; FAQ "Will La Nina follow?" |
| el nino map, sea surface temperature anomaly map, el nino satellite | `/map` | event counts + red/orange alerts in the summary |
| what is el nino, el nino explained, enso faq, el nino myths | `/learn` (+ 243 topic URLs) | FAQPage markup, glossary, myths |
| koh samui webcam, gulf of thailand webcam | `/cams` | cam list in the summary |

Writing rules that keep this working: English only, the house spelling "El Nino" in
titles (with "El Niño" allowed inside body text once, since people search both), numbers
with units and dates, no em dashes. Titles state the year ("2026-27") because the event
name is the query. Each new Learn topic is automatically a new indexable URL.

Internal linking: every summary ends with a nav to the 11 pages; the Learn summary links
every topic; each topic links its `related` topics and the index table links its
explainers. This is the crawl graph, no separate "SEO links" are needed.

## 5. Search engines: what the owner does once (on the final domain)

Do this AFTER the move to `elnino.soclose.co` (a property on the sslip.io name would
have to be redone).

Google Search Console (search.google.com/search-console):
1. Add property. Either a URL-prefix property `https://elnino.soclose.co/` verified with
   the HTML tag: copy the `content` value into `GOOGLE_SITE_VERIFICATION=` in
   `/opt/elnino/.env`, restart, click Verify (the meta tag is on every page). Or a
   Domain property `soclose.co` verified by a DNS TXT record at IONOS (covers every
   subdomain; recommended if other SoClose sites will be added).
2. Sitemaps -> submit `https://elnino.soclose.co/sitemap.xml`.
3. URL inspection on `/`, `/samui`, `/learn/oni` -> "Request indexing" (only for the
   first few; the sitemap does the rest).
4. Enhancements: check the Dataset, FAQ and Breadcrumb reports after a week; validate
   one URL at search.google.com/test/rich-results.

Bing Webmaster Tools (bing.com/webmasters): "Import from Google Search Console" (one
click) or add the site and verify with the meta tag (`BING_SITE_VERIFICATION=`), then
submit the sitemap. Bing feeds DuckDuckGo, Yahoo, Ecosia and the Copilot answers.

Google Dataset Search picks up the Dataset markup from the normal crawl, nothing to submit.

## 6. IndexNow (instant notification of changed URLs)

Implemented in `seo.py`: `indexnow_enabled()` is true only when `INDEXNOW_KEY` (8-128
`[A-Za-z0-9-]`) is set AND `PUBLIC_ORIGIN` is not a disposable host (sslip.io, nip.io,
localhost). The key file is served at `/<key>.txt`. After every collector round the post
hook compares each page's `lastmod` with the previous round and POSTs the changed URLs
(+ `/sitemap.xml`) to `https://api.indexnow.org/indexnow` (one call reaches Bing,
Yandex, Seznam, Naver). Google does not use IndexNow; the sitemap `lastmod` covers it.

Enable on the final domain: `INDEXNOW_KEY=$(openssl rand -hex 16)` in `/opt/elnino/.env`,
restart, check `curl https://elnino.soclose.co/<key>.txt` returns the key. The log line
`indexnow: N URLs -> HTTP 202` confirms a ping (200/202 = accepted).

## 7. Integration lines for the frontend (Layout / pages, not edited by the SEO work)

`frontend/src/components/Layout.tsx`:

```tsx
import { useSeo } from '../seo'
// inside Layout(), replace `usePageTitle(loc.pathname)` with:
useSeo()
// (and delete usePageTitle + TITLES, or keep TITLES for the nav only)
```

`frontend/src/main.tsx`, so `/learn/<id>` opens the Learn page (the server already
renders it; without this route the SPA shows "Page not found" after hydration):

```tsx
['/learn', Learn], ['/learn/:topic', Learn],
```

`frontend/src/pages/Learn.tsx`:

```tsx
import { useParams } from 'react-router-dom'
import { useSeo } from '../seo'
// inside Learn():
const { topic: topicParam } = useParams()
const topic = getTopic(topicParam)
useSeo(topic
  ? { title: `${topic.title}: El Nino explained`.slice(0, 60), description: topic.short.slice(0, 160), path: `/learn/${topic.id}` }
  : undefined)
// remove the `document.title = 'Learn · El Nino Watch'` effect, and in the hash effect:
const id = topicParam ?? decodeURIComponent(loc.hash.replace(/^#/, ''))
```

Optional: the not-found page can call `useSeo({ noindex: true })`.

## 8. Moving to elnino.soclose.co (redirect the sslip name)

1. IONOS DNS: `A elnino -> <vps-ip>` (DEPLOY.md, "Adding elnino.soclose.co").
2. Certificate: `certbot --nginx --expand -d elnino.soclose.co -d elnino.soclose.co`.
3. `/opt/elnino/.env`: `PUBLIC_ORIGIN=https://elnino.soclose.co`, restart `elnino-watch`.
4. nginx: serve the app on the new name only and 301 the old one, so search engines
   transfer the signals (Google treats a site-wide 301 as a move; keep it for a year):

```nginx
# /etc/nginx/sites-available/elnino  (certbot keeps its own 443 listen lines)
server {
    listen 443 ssl http2;
    server_name elnino.soclose.co;
    # ssl_certificate lines as written by certbot
    return 301 https://elnino.soclose.co$request_uri;
}
server {
    listen 80;
    server_name elnino.soclose.co elnino.soclose.co;
    return 301 https://elnino.soclose.co$request_uri;
}
server {
    listen 443 ssl http2;
    server_name elnino.soclose.co;
    # ssl_certificate lines as written by certbot
    location / { proxy_pass http://127.0.0.1:8911; proxy_set_header Host $host;
                 proxy_set_header X-Forwarded-Proto https; }
}
```

5. Search Console: add the new property (section 5); in the old sslip property, if one
   was made, use "Change of address". Then re-submit the sitemap.

## 9. Verification (run on 2026-09-24 against a local PUBLIC_MODE instance)

- `cd backend && uv run pytest -q tests/test_seo.py`: 23 passed; full suite green except
  4 failures in `tests/test_analogs.py` (another agent's new module, unrelated).
- `uv run ruff check app/seo.py app/config.py tests/test_seo.py`: clean.
- Every route curled: correct `<title>`, canonical, OG, JSON-LD parses, the summary
  shows the live ONI +1.80 °C (JJA 2026), RONI +1.36 °C, Nino 3.4 +3.0 °C (week of 16 Sep
  2026), CPC "El Niño Advisory (issued 10 Sep 2026)", Samui "Prepare" with times.
  Sitemap: 253 URLs. `/carte` and `/map/` -> 301. `/learn/nope` -> 404 + noindex.
- JSON-LD structure check over the 10 pages + 40 topic pages: 0 problems (required
  fields per type, absolute URLs, unique `@id`, breadcrumb positions, hash of every
  injected script equals the hash in the CSP header).
- Playwright (headless Chromium) on `/`, `/learn`, `/samui`, `/learn/oni`, `/map`:
  0 `securitypolicyviolation` events, 0 CSP console messages, 0 console errors, 0 page
  errors; the app mounts and replaces the summary on every route.
- Lighthouse 12 (`npx lighthouse@12 <url> [--preset=desktop]`, local PUBLIC_MODE instance on
  8951, Chrome headless, 24 Sep 2026). "Before" = the state described in the previous
  version of this section; "after" = after the CLS / a11y / lazy-map work of the same day:

| Page | Perf desktop | Perf mobile | A11y | Best practices | SEO | CLS desktop |
|---|---|---|---|---|---|---|
| `/` | 63 -> **87** | 38 -> 63 | 88 -> **100** | 100 | 100 | 1.92 -> **0.003** |
| `/samui` | 83 -> **91** | 59 -> 63 | 87 -> **100** | 100 | 100 | 0.167 -> **0.001** |
| `/map` | 91 -> 88 | 46 -> 52 | 95 -> **100** | 100 (mobile 96 -> 100) | 100 | 0.103 -> **0.006** |
| `/history` (new) | **92** | 63 | **100** | 100 | 100 | 0.001 |
| `/learn` | 97 | 65 | 97 -> **100** | 100 | 100 | 0.001 |

  What changed (frontend, not the SEO files): the briefing card is a fixed-height collapsed
  block (same height as its skeleton, "Show all sections" expands it), every async block on
  the Overview and the Samui page reserves its loaded height, the tour spotlight and card are
  positioned with transforms (their moves are not layout shifts), the map's layer list
  reserves its height; the maplibre chunk (1 MB) and the event list are only fetched once the
  mini map is in view AND the person has scrolled or moved the pointer (a "Show the map"
  button in the placeholder loads it on demand); `role=radio` chips no longer carry
  `aria-pressed`, zero-count chips keep a readable colour (dashed border instead of 50 %
  opacity), help "?" buttons are 24 x 24 px around the 16 px dot, inline links have a 24 px
  hit box (`padding-block`, list links `inline-block`), the header stale / failing chips
  have visible-text accessible names, `/samui` uses `h2` after the `h1`, kind badges and
  the "wet" seasonal colour use `toneText()` (>= 4.5:1 in both themes), map DOM labels are
  named by their text, the smallest labels read at 12 px on phones. Mobile performance is
  bounded by the JS bundle on a throttled 4G / slow CPU profile (LCP 6-10 s: `index`
  712 KB + `charts` 417 KB); a code-split of recharts per page would be the next step.
  "Text compression" and "long cache TTL" remain local artifacts (nginx handles both).
- Headless Chromium (Playwright) on the 11 pages at 360 / 390 / 768 / 1440 / 1920 / 2560 px:
  0 `securitypolicyviolation` events, 0 CSP console messages, 0 console errors, 0 page
  errors, no horizontal overflow, `window.__helpGaps` empty (the `sla_*` sea-level series
  now resolve to their topics).

## 10. Things outside the SEO files (for the reviewers)

- `security.py` could add `X-Robots-Tag: noindex` on `/api/*` responses as a belt to the
  robots.txt braces (harmless, one header).
- The SPA catch-all returns HTTP 200 + index.html for unknown paths (`/foo`), a soft
  404. Known routes are handled by `seo.py`; the catch-all could answer 404 for paths
  without a file extension that are not in `seo.ROUTES` and not `/learn/*`.
