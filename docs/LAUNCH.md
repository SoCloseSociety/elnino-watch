# Launch and visibility plan

Drafts and checklists only. Nothing here has been posted or submitted. Dates assume the
public repository goes live at https://github.com/SoCloseSociety/elnino-watch with the site
at https://elnino.soclose.co. Replace `<date>` and the numbers (ONI, Nino 3.4, level) with
the live values on the day you post: every draft quotes figures, and the figures must be
the ones the site shows at that moment (project rule: never quote a number you did not
check).

## 1. GitHub repository settings (day 0)

- **Name**: `elnino-watch`. **Visibility**: public.
- **Description** (<= 350 chars):
  `Live El Nino (ENSO) tracker with an explainable, sourced risk watch for Koh Samui, Thailand. 85 free public sources (NOAA, NASA, BoM, JMA, IRI, Copernicus, Open-Meteo, GDACS, TMD ...), 22 satellite map layers, 240 plain-English help topics. Every number dated, sourced, explained. FastAPI + React + MapLibre. Not an official warning service.`
- **Homepage**: https://elnino.soclose.co
- **Topics** (20 max on GitHub; pick from):
  `el-nino`, `enso`, `climate`, `weather`, `climate-data`, `thailand`, `koh-samui`,
  `nasa`, `noaa`, `open-data`, `dashboard`, `fastapi`, `react`, `maplibre`, `typescript`,
  `python`, `disaster-preparedness`, `early-warning`, `oceanography`, `sea-surface-temperature`.
  (Alternates if room: `nasa-gibs`, `open-meteo`, `risk-assessment`, `self-hosted`.)
- **Social preview**: upload `docs/social-preview.png` (1280 x 640) in Settings > General.
- **Features**: Issues on, Discussions on (categories: Q&A, Data sources, Show and tell),
  Wiki off, Projects off. Sponsorships: optional.
- **Security**: enable private vulnerability reporting (SECURITY.md points there),
  Dependabot alerts and security updates, secret scanning + push protection.
- **Branch protection on `main`**: require the CI workflow to pass, no force pushes.
- **Releases**: tag `v0.1.0` after the first push ("first public release"); GitHub
  generates release notes. A release makes the repo show up in "recent releases" feeds.
- **Pin** the repository on the organisation profile (Settings of the org > pinned).
- Add the org README patch (`ORG_README_PATCH.md`) in the same hour, so the profile links
  to the new repo while it is fresh.

## 2. Awesome lists (verified to exist on 2026-09-25, all accept PRs)

Read each list's CONTRIBUTING first; one PR per list; describe in one line; do not
oversell. Suggested one-liner:
`[El Nino Watch](https://github.com/SoCloseSociety/elnino-watch) - Live El Nino / ENSO tracker built on 85 free public sources (NOAA, NASA, Copernicus, Open-Meteo ...) with an explainable local risk watch for Koh Samui, Thailand. FastAPI + React + MapLibre, MIT.`

| List | Stars (2026-09) | Where it fits | Note |
|---|---|---|---|
| [protontypes/open-sustainable-technology](https://github.com/protontypes/open-sustainable-technology) | 2.5k | "Climate Data Processing and Access" or "Natural Hazard and Storm" sections | The most relevant. Strict quality bar (activity, licence, docs); they check that the project is actively maintained. Apply after the first release and a few commits of public history. |
| [pangeo-data/awesome-open-climate-science](https://github.com/pangeo-data/awesome-open-climate-science) | 600 | Tools / visualisation | Community list run by Pangeo; short PR. |
| [sacridini/Awesome-Geospatial](https://github.com/sacridini/Awesome-Geospatial) | 5.3k | "Web Map Development" or a "Climate / Weather" entry | Very broad list; the MapLibre + NASA GIBS angle fits. |
| [softwareunderground/awesome-open-geoscience](https://github.com/softwareunderground/awesome-open-geoscience) | 1.8k | "Meteorology / climate" | Geoscience audience; mention the ERA5 analogs page. |
| [DaveParr/awesome-climate-data](https://github.com/DaveParr/awesome-climate-data) | 30 | Tools that aggregate climate datasets | Small but on-topic (the name in the brief); check it is still maintained (last push 2026-06). |
| [philsturgeon/awesome-earth](https://github.com/philsturgeon/awesome-earth) | 1.4k | "Adaptation" / "Tools" | Action-oriented list; frame it as preparedness for a climate event. |
| [public-apis/public-apis](https://github.com/public-apis/public-apis) | 483k | Weather / Environment | Only if you want to advertise the six cached JSON endpoints as a public API; they are rate-limited (10 r/s). Probably wait. |

Not found (checked): `awesome-weather` (no maintained general list under that name; the
hits are ML-paper lists), `awesome-climate` (404). `awesome-thailand` lists exist but are
dormant (last push 2023) and dev-tool oriented.

## 3. Hacker News: "Show HN" draft

Post as the maintainer, on a weekday morning US time (14:00-16:00 UTC). Title <= 80 chars,
no marketing words, the URL is the live site (HN prefers the product), first comment
explains and links the repo. Answer every comment for the first two hours.

**Title options**

- `Show HN: El Nino Watch -- a live ENSO tracker with an explainable risk level for one island`
- `Show HN: Tracking the 2026 El Nino from 85 free public sources, with every number sourced`

**First comment (draft)**

> I live on Koh Samui, in the Gulf of Thailand. A strong El Nino is under way (NOAA's ONI is at +1.80 for Jun-Aug 2026), and for this island that usually means a weak rainy season followed by a long, hot dry season: water rationing, sometimes bleaching and haze. I could not find one place that put the official numbers, the forecasts and the local signals together, so I built it.
>
> What it does: polls 85 free, keyless public sources (NOAA CPC/PSL/PMEL, NASA EONET/FIRMS/GIBS, BoM, JMA, IRI, WMO, Copernicus, Open-Meteo, GDACS, USGS, the Thai met office and water authorities, plus news and social feeds) at the rate each one really updates, stores everything in SQLite with its timestamp and source URL, and turns the local inputs into a five-level "watch" (normal, vigilance, prepare, act, leave). Every factor shows its raw value, the threshold it crossed, the period it describes, whether it is observed / forecast / reanalysis / bulletin, and a link. If a critical input is missing, the level is "unknown", never "normal".
>
> Rules I stuck to: never fabricate a value (tests use captured real payloads, none touch the network), freshness is shown as data (stale sources are marked stale), and nothing ships without a plain-English explanation (240 help topics, written for people who are not meteorologists). There is also a page that replays the seven strong El Ninos since 1982 for this island from the same ERA5 grid cell, with 48 documented impacts and their sources.
>
> Stack: FastAPI + stdlib sqlite3, React 19 + MapLibre + NASA GIBS tiles, one small VPS, ~550 MB RAM. MIT. Point it at another place with three env vars.
>
> Not an official warning service; it says so on every page. I would love scrutiny on the thresholds (they are documented next to each factor) and pointers to sources I missed, especially Southeast Asian ones.
>
> Repo: https://github.com/SoCloseSociety/elnino-watch

Expect questions on: the LLM briefing (answer: optional, rules text is the default, any
number not in the rules text is rejected), Open-Meteo's free tier (answer: heavy requests
are spread out, one per hour), why SQLite (answer: single writer, WAL, 550 MB box).

## 4. Reddit drafts

Each subreddit has its own rules; the drafts follow them. Post from a real account with
history, one subreddit per day, reply to every comment, never cross-post the same text.

**r/dataisbeautiful** (rules: original content must be tagged `[OC]`, the title must
describe the visual, the tool and data source go in a comment, no dashboards-as-ads: post
one chart, not the site). Post an image, not a link.

- Image: the "Past El Ninos" seasonal chart (Feb-Apr rain as % of the 1991-2020 normal for
  the 7 strong El Ninos and the neutral median), exported from `/history`.
- Title: `[OC] Koh Samui's dry-season rain in the 7 strong El Ninos since 1982, as a percentage of normal (ERA5 reanalysis)`
- Comment: `Data: ECMWF ERA5 via the Open-Meteo archive (one 30 km grid cell), El Nino strength from NOAA CPC's ONI. Tool: an open-source tracker I built (FastAPI + React), link in my profile / on request. In 6 of 7 events the Feb-Apr total was below 60% of normal; the neutral-year median is 66% (n=18).`
  (Check the two figures on the page the day you post.)

**r/Thailand** (rules: no self-promotion spam; useful, local content is welcome; flair
"News" or "Discussion"). Link post to the live site is acceptable if the text explains why
it is useful.

- Title: `I built a free, open tracker for the 2026 El Nino and what it means for Samui and the South (water, heat, rain, ferries), all from official sources`
- Body: three sentences on what it shows, one on what it is not (not an official warning
  service; TMD, PWA and DDPM first), one asking for local sources you missed (provincial
  water notices, Thai-language feeds).

**r/kohsamui** (small, practical). Same as above, shorter, plus the direct link to
`/samui` and `/prep`. Ask residents to sanity-check the preparedness list and the shops.

**r/weather** (rules: discussion of weather; self-promotion limited, must be
educational). Post the ENSO explainer angle: `An open-source dashboard that shows every ENSO index (ONI, RONI, Nino 3.4 weekly and daily, SOI, MEI, WWV, heat content, MJO) with its source and period, updated at each agency's real cadence`, link to `/indices` and `/learn`.

**r/climate** (rules: climate-related, no low-effort links). Post the "Past El Ninos"
analysis with the method section, link to `/history`; keep the tone analytical.

Others worth a look: r/opensource (Show-and-tell flair), r/selfhosted ("point it at your
own place"), r/Python and r/reactjs (technical write-up, once there is a blog post),
r/TropicalWeather (during the NE-monsoon season, when a storm is near the Gulf).

## 5. Social posts (drafts, <= 280 chars where it matters)

**X / Bluesky (thread, 4 posts)**

1. `A strong El Nino is under way (NOAA ONI +1.80, JJA 2026). I built an open-source tracker that follows it from 85 free public sources and turns it into a plain risk level for Koh Samui. Live: https://elnino.soclose.co  Code (MIT): https://github.com/SoCloseSociety/elnino-watch`
2. `Every number shows its date, its period, whether it is observed or a forecast, and a link to the file it came from. Missing data = "unknown", never "normal". Tests use captured real payloads and never touch the network.` + screenshot `samui-watch.png`
3. `22 satellite layers (NASA GIBS: SST anomaly, IMERG rain, Himawari IR, true colour, soil moisture, floods, fires) and 1,800+ hazard events on one MapLibre map.` + screenshot `map-sst-anomaly.png`
4. `The 7 strong El Ninos since 1982 replayed for the island from ERA5: rain vs normal by season, heat, dry spells, 48 documented impacts with their sources. Not a forecast, a range of precedents.` + screenshot `past-el-ninos.png`

Tag / mention only where it is relevant and true: @NWSCPC (NOAA CPC) and @NASAEarth data
credit, Open-Meteo, MapLibre. Hashtags: #ElNino #ENSO #KohSamui #OpenData #OpenSource.

**Mastodon** (500 chars; the fediverse likes the "no tracking, self-hostable, open data"
angle): post 1 + "Self-hostable on a 1 GB VPS, no API keys, no tracking, CSP-strict.
Attribution to every provider on the Sources page." Post to the #ElNino, #ENSO,
#OpenData, #Climate hashtags (the app itself follows the #ElNino tag timeline, so the post
will show up in its own feed; that is fine, it is a real post).

**LinkedIn** (longer, professional): the engineering angle (freshness as data, provenance
vocabulary, rules briefing with an LLM guard, accessibility 100, SEO with server-rendered
summaries). Link the repo.

## 6. Product Hunt

Category: Open Source / Data & Analytics. Tagline (<= 60 chars):
`Live El Nino tracker with a sourced local risk watch`. Gallery: the five screenshots
plus `social-preview.png` as the thumbnail. First comment = the Show HN text, shorter.
Launch on a Tuesday-Thursday, 00:01 PT. Product Hunt rewards a maker who answers
comments all day; only launch if someone can. Honest expectation for a niche tool: a
few dozen upvotes; the value is the backlink and the listing.

## 7. Search engines (site)

Everything technical is already in place (`backend/docs/SEO.md`): server-rendered
summaries, JSON-LD, sitemap with real `lastmod`, robots, OG image, IndexNow. What remains
is done by hand once:

1. **Google Search Console**: add a URL-prefix property for `https://elnino.soclose.co/`,
   verify with the HTML-tag method (`GOOGLE_SITE_VERIFICATION` in `.env`, restart), then
   submit `https://elnino.soclose.co/sitemap.xml`. Request indexing for `/`, `/samui`,
   `/history`, `/learn`. Watch the "Pages" report for soft 404s (the SPA catch-all).
2. **Bing Webmaster Tools**: import from Search Console (one click), or verify with
   `BING_SITE_VERIFICATION`. Bing feeds DuckDuckGo and Yahoo.
3. **IndexNow**: set `INDEXNOW_KEY` (16-64 hex chars) in `.env`; the app pings on data
   changes when `PUBLIC_ORIGIN` is the final domain. Verify with
   `curl https://elnino.soclose.co/<key>.txt`.
4. **Google Dataset Search** needs nothing else: the six JSON endpoints are declared as
   `Dataset` distributions in the JSON-LD; check with the Rich Results test on `/indices`.
5. **Backlinks that matter for this niche**: the awesome lists above, the GitHub org
   profile, a mention in the Open-Meteo "showcase" (they list projects that use their API:
   open an issue or PR on their docs), NASA GIBS "applications" page (email the GIBS team),
   Climate Reanalyzer's "used by" (email). Each one is a real, relevant referrer.

## 8. Content ideas after launch (each is a post and a backlink)

- "Freshness is part of the data": how 85 collectors declare their real cadence and what
  "stale" means per source.
- "Provenance vocabulary for a weather dashboard": observed / forecast / model_analysis /
  reanalysis / bulletin, and why today's daily maximum is a forecast.
- "A rules briefing with an LLM guard": how the LLM rewrite is rejected when it invents a
  number.
- "Replaying seven El Ninos on one ERA5 cell": method, limits, what it does and does not
  say.
- A monthly "El Nino and Samui" note during the 2026-27 dry season, with the live numbers.

## 9. What not to do

- Do not post the same text to several subreddits or on the same day.
- Do not claim it is a warning service, a forecast, or "the most complete" anything.
- Do not quote a number that is not on the site at the moment of posting.
- Do not add the project to a list whose scope it does not fit (ML paper lists, dormant
  lists) just to get a link.
