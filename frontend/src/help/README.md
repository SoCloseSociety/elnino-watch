# Help system (`src/help/`)

Plain-English explanations for every number, chart, map layer and rule in the
dashboard, for owners who are not meteorologists. No new npm dependency.

## Files

| File | What it is |
|---|---|
| `types.ts` | `TopicDef`, `Topic`, `PageId`, `TourStep`, category labels |
| `topics/*.ts` | The topic texts, by domain (`enso`, `indices`, `forecasts`, `ocean_hazards`, `samui`, `data_prep`, `places`, `shopping`, `analogs` = the Past El Ninos page's tables, charts, colour scale, timeline and loading state, `extra` = map tile providers, climate context, Sources columns, Cams, public site). `topics/enso.ts` also holds `SRC`, the shared source links (checked 2026-09-24). |
| `content.ts` | Registry: `TOPICS`, `TopicId` type, `getTopic`, `allTopics`, `searchTopics`, `validateTopics`, lookup maps (`FACTOR_TOPIC`, `LAYER_TOPIC`, `PREP_TOPIC`, `SERIES_TOPIC`, `STATUS_TOPIC`, `topicFor`), `LEVEL_ACTIONS`, `FACTOR_ACTIONS`, `FAQ`, `MYTHS` |
| `guides.ts` | `PAGE_GUIDES` (the "How to read this page" text) and `TOURS` (tour steps per page), `pageFromPath` |
| `store.ts` | Framework-free store: `openTopic`, `closeTopic`, `startTour`, `endTour`, `useHelp()`, localStorage helpers |
| `HelpTip.tsx` | `<HelpTip id>` "?" button + popover, and `<Term id>` inline glossary term |
| `HelpDrawer.tsx` | Global side drawer that shows a full topic |
| `PageGuide.tsx` | Collapsible "How to read this page" panel |
| `Tour.tsx` | Guided tour overlay (spotlight on `data-tour` elements) |
| `TopicView.tsx`, `Markdown.tsx` | Rendering of a topic (used by the drawer and the Learn page) |
| `EnsoDiagram.tsx` | Inline SVG: normal vs El Nino conditions (used by the Learn page) |
| `index.ts` | Public exports: `import { HelpTip, PageGuide, ... } from '../help'` |
| `../pages/Learn.tsx` | The `/learn` page (default export) |

## Integration (4 steps)

### 1. Route `/learn` (`src/main.tsx`)

```tsx
const Learn = lazy(() => import('./pages/Learn'))
// add to the route list:
['/learn', Learn],
```

Also add `'/learn': 'Learn'` to `TITLES` in `Layout.tsx` (Learn sets `document.title` itself too),
and a nav entry "Learn" in `NAV`. Put `data-tour="help-learn"` on that nav link (the last
step of the Overview tour points at it).

### 2. Mount the drawer and the tour ONCE (`src/components/Layout.tsx`)

Both must be inside the router (Layout already is):

```tsx
import { HelpDrawer, Tour } from '../help'
// at the end of Layout's returned JSX:
<HelpDrawer />
<Tour />            {/* auto-starts once on the first visit of "/" (overview) */}
```

`<Tour autoStart={['overview']} autoStartDelayMs={1500} />` are the defaults. Pass
`autoStart={[]}` to disable auto-start. While `HelpDrawer` is mounted, every "Learn more"
opens the drawer; without it, "Learn more" links to `/learn#<id>`.

Optional: a "?" button in the header that starts the tour of the current page:

```tsx
import { startTour, pageFromPath } from '../help'
const p = pageFromPath(loc.pathname)
{p && <button className="btn" onClick={() => startTour(p)}>Tour</button>}
```

### 3. One `PageGuide` at the top of each page (under `PageHeader`)

```tsx
import { PageGuide } from '../help'
<PageGuide page="overview" />   // overview | map | indices | news | samui | history | prep | sources | places | cams
```

It remembers its collapsed state per page (`localStorage` key
`elnino.help.guide.<page>.collapsed`) and has a "Take the tour" button.
On the Map page (full-bleed), put it in the side panel or use `defaultOpen={false}`.

### 4. `HelpTip`s next to the things they explain, and `data-tour` attributes

```tsx
import { HelpTip, Term, topicFor, FACTOR_TOPIC, LAYER_TOPIC } from '../help'

<Card title={<>ENSO probabilities (IRI) <HelpTip id="iri_plume" /></>}> ... </Card>
<p>Values are an <Term id="anomaly">anomaly</Term>.</p>
{factors.map(f => <FactorCard ... right={<HelpTip id={FACTOR_TOPIC[f.id] ?? 'risk_factors'} />} />)}
{layers.map(l => <label>{l.title} {LAYER_TOPIC[l.id] && <HelpTip id={LAYER_TOPIC[l.id]} />}</label>)}
```

`HelpTip` props: `id` (a `TopicId`, typo = compile error), `label?` (accessible name,
default "What is <title>?"), `size?: 'sm' | 'md'`, `learnMore?: 'auto' | 'drawer' | 'page'`,
`className?`. The button stops click propagation, so it is safe inside clickable headers
or `<summary>`. On phones (< 640 px) the popover is a bottom sheet.

`topicFor(appId)` resolves any app id (risk factor id, layer id, prep category id, series
name, status key, or a topic id) to a topic id, or `null`.

Open a topic from code: `openTopic('oni')` (or `useHelp().openTopic`).

## Where to put which HelpTip (topic ids per page element)

**Overview (`/`)**
| Element | Topic id |
|---|---|
| Koh Samui watch card / level badge | `risk_levels` |
| Briefing | `limitations` (or `sources_disagree`) |
| Weekly Nino 3.4 value / "Change from the previous week" | `nino34` (+ `time_resolution`) |
| ENSO probabilities (IRI) | `iri_plume` (season labels: `season_codes`) |
| NOAA status (Watch/Advisory) | `cpc_alert_system` |
| "Departure from climatology" | `anomaly` / `climatology_baseline` |
| "ONI: current event vs major El Ninos" | `past_events` (+ `oni`) |
| SOI / MEI.v2 / RONI mini-cards | `soi` (`bom_soi` if BoM), `mei_v2`, `roni` |
| Latest alerts | `gdacs` |
| Official bulletins and press | `news_signals` |
| Map card | `map_overlays` |
| Any "stale" chip / "as of" line | `stale_data` / `freshness` |

**Map (`/map`)**
| Element | Topic id |
|---|---|
| Satellite layer list, per layer | `LAYER_TOPIC[layer.id]` (`layer_sst_anomaly`, `layer_sst`, `layer_imerg`, `layer_himawari_ir`, `layer_truecolor`, `layer_aerosol`, `layer_chlorophyll`, `layer_soil_moisture`, `layer_land_temp`, `layer_radar`) |
| Vector data: Nino boxes / impact zones / home circle | `nino_regions` / `teleconnections` / `map_overlays` |
| Events (GDACS, EONET, FIRMS) | `gdacs`, `eonet`, `firms_fires` |
| Buoys | `tao_buoys` |

**Indices (`/indices`)**: group headings via `SERIES_TOPIC[series]` or: ONI `oni`, RONI `roni`,
weekly Nino groups `nino_regions` (per region `nino12`, `nino3`, `nino34`, `nino4`), SOI `soi`,
BoM SOI `bom_soi`, MEI `mei_v2`, world SST `world_sst`, TAO `tao_buoys`, neutral band `neutral`,
period selector `time_resolution`.

**News (`/news`)**: page header `news_signals`; "official" kind `cpc_alert_system` / `wmo_update`.

**Koh Samui (`/samui`)**
| Element | Topic id |
|---|---|
| Overall level badge / headline | `risk_levels` (Unknown state: `unknown_level`) |
| Rules fired | `risk_rules` |
| "What to do now" | `risk_levels` |
| "What would raise the level" | `risk_rules` |
| Factors heading | `risk_factors`; each factor: `FACTOR_TOPIC[f.id]` |
| Coverage / missing factors | `data_coverage` |
| Level history | `risk_levels` |
| Water: rainfall totals vs normal | `rain_vs_normal` (+ `era5`) |
| TMD weather warnings | `tmd_warnings` (rain amounts: `rain_classes`) |
| Seasonal outlook (6 months) | `seasonal_outlook` |
| Local weather: feels-like / PM2.5 / waves | `heat_index` / `pm25` (AQI: `aqi`) / `wave_height` |
| Season note | `samui_seasons` |
| Exit view: recommendation / signals | `exit_plan` |
| Exit view: departure windows | `departure_windows` |
| Water supply context | `samui_water_supply` |

**Past El Ninos (`/history`)**: page guide `history`. Status card `analogs_history_status`; takeaways `analogs` (+ `analogs_reading`);
events table `analogs_events_table` (+ `strength_categories`, terms `oni` / `roni`); Samui metrics table `analogs_colour_scale`
(+ `rain_vs_normal`, term `heat_index`); monthly charts `analogs_charts` (+ `climatology_baseline`, `heat_index`); impacts
timeline and "not found" list `analogs_impacts` (impact types: `samui_water_supply`, `factor_water`, `factor_flood`,
`tropical_cyclone`, `asmc_haze`, `factor_heat`, `coral_reef_watch`); method `analogs_reading` + `analogs_limits`; the
"documented" kind badge resolves to `analogs_impacts` via `VALUE_KIND_TOPIC`. The compact card on Overview / Samui: `analogs`.

**Preparedness (`/prep`)**: page `preparedness`; each category `PREP_TOPIC[category.id]`
(`prep_water`, `prep_food`, `prep_power`, `prep_health`, `prep_heat`, `prep_haze`, `prep_flood`,
`prep_comms`, `prep_money`, `prep_exit`, `prep_documents`, `prep_home_pets`).

**Sources (`/sources`)**: state chips `sources_page`; freshness column `freshness`; stale `stale_data`;
"numbers differ" note `sources_disagree`; model sources `model_vs_observation`, `era5`, `cams`, `open_meteo`.

## `data-tour` attributes to add

A missing target does not break a tour (the step is shown centred with a note), but the
spotlight only works once the attribute exists. Put it on the element to highlight:

| Page | `data-tour` value | Element |
|---|---|---|
| overview | `overview-samui` | Koh Samui watch card |
| overview | `overview-briefing` | Briefing block |
| overview | `overview-weekly` | "Change from the previous week" card (weekly Nino 3.4) |
| overview | `overview-iri` | "ENSO probabilities (IRI)" card |
| overview | `overview-oni-compare` | "ONI: current event vs major El Ninos" card |
| overview | `overview-analogs` | "What past El Ninos did to Samui" card |
| overview | `overview-alerts` | "Latest alerts" card |
| overview | `help-learn` | "Learn" nav link (sidebar; mobile nav if it is the visible one) |
| map | `map-canvas` | Map container |
| map | `map-layer-picker` | "Satellite layer" section of the side panel |
| map | `map-date` | Date slider |
| map | `map-legend` | Layer legend |
| map | `map-vector` | "Vector data" section |
| indices | `indices-range` | Period selector (`Seg` in the header) |
| indices | `indices-groups` | The group chips `<nav>` |
| indices | `indices-chart` | The first chart (only one element should carry it) |
| news | `news-filters` | Filter bar |
| news | `news-list` | Feed list |
| samui | `samui-level` | Overall level badge + headline block |
| samui | `samui-actions` | "What to do now" block |
| samui | `samui-triggers` | "What would raise the level" block |
| samui | `samui-factors` | Factors section |
| samui | `samui-water` | "Water: rainfall totals vs normal" card |
| samui | `samui-analogs` | "What past El Ninos did to Samui" card |
| samui | `samui-exit-tab` | The tab/button that switches to the exit view |
| history | `history-takeaways`, `history-events`, `history-metrics`, `history-charts`, `history-impacts`, `history-method` | Takeaways card, events table, Samui metrics table, the charts section, impacts timeline, method card |
| prep | `prep-household` | "Household" card |
| prep | `prep-progress` | "Progress" card |
| prep | `prep-categories` | The categories list/grid |
| prep | `prep-scenarios` | "Scenarios" card |
| prep | `prep-contacts` | "Emergency contacts" card |
| sources | `sources-summary` | Summary counts / state filter bar |
| sources | `sources-table` | The sources table/list |
| sources | `sources-verify` | "Verify all" button (on the public site: the "reserved for the site owner" note) |
| prep | `prep-budget` | "Shopping budget" card |
| places | `places-cards`, `places-matrix`, `places-ranking`, `places-map`, `places-add`, `places-enso` | Place cards, comparison matrix, ranking, map, "Add a place", El Nino panel |
| cams | `cams-filters`, `cams-grid` | Filter bar, camera grid |

The same list is available at runtime: `allTourTargets()`.

## Links into the Learn page

`/learn#<topic_id>` opens that glossary entry (for example `/learn#roni`). Sections:
`#el-nino-in-5-minutes`, `#reading-this-dashboard`, `#risk-levels`, `#what-to-do`,
`#glossary`, `#faq` (each question `#faq-<id>`), `#myths`, `#limitations`, `#sources`.

## Editing content

- Text fields use markdown-lite: blank line = paragraph, `- ` bullet (and `  - ` nested),
  `**bold**`, `[text](https://...)`, `[[topic_id]]` or `[[topic_id|label]]`.
- English only, no em dashes (use `--`), numbers with units, every topic cites 1-3 real sources.
- Run `validateTopics()` (returns `[]` when every related id and `[[link]]` resolves and no em dash is present).
- **Keep in sync with the backend.** The factor thresholds, caps, rules R1-R4, critical factors,
  `LEVEL_ACTIONS` and `FACTOR_ACTIONS` mirror `backend/app/local/risk.py`, and the exit-plan
  thresholds mirror `backend/app/local/exit.py`, as read on 2026-09-24. If those files change,
  update `topics/samui.ts` and `content.ts`.

## Accessibility

- HelpTip / Term: real `<button>`s with `aria-haspopup="dialog"`, `aria-expanded`,
  `aria-controls`; popover `role="dialog"` labelled by its title; Escape closes and returns
  focus; outside click closes; bottom sheet on phones.
- Drawer and tour: `role="dialog"` + `aria-modal`, focus moved in and trapped, Escape closes,
  focus restored on close. Tour: arrow keys Next/Back, respects `prefers-reduced-motion`.
- All colours come from the theme tokens in `index.css`, so dark and light themes both work.
