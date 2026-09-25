import type { TopicDef } from '../types'
import { SRC } from './enso'

/*
 * Help for the elements of the "Past El Ninos" page (/history). The three method topics
 * (analogs, analogs_reading, analogs_limits) are written by the backend in
 * backend/docs/help_topics/*.md and imported into topics/backend.ts; these cover the
 * page's own tables, charts, colour scale, timeline and loading state.
 * Numbers quoted here are the ones the endpoint computes (docs/reports/REVIEW_2026-09-24.md,
 * section 4, 2026-09-24); the page always shows the live payload, never these.
 */

const SRC_ANALOGS = {
  oniTable: { title: 'NOAA CPC -- cold and warm episodes by season (ONI table)', url: 'https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php' },
  bp2016: { title: 'Bangkok Post, 10/10/2016 -- Severe water shortage on Koh Samui', url: 'https://www.bangkokpost.com/thailand/general/1107052/severe-water-shortage-on-koh-samui' },
  wmoDry: { title: 'WMO -- Guidelines on the definition and monitoring of extreme weather and climate events (dry spell)', url: 'https://library.wmo.int/idurl/4/58396' },
  chartsCls: { title: 'web.dev -- Cumulative Layout Shift (why chart boxes are reserved)', url: 'https://web.dev/articles/cls' },
}

export const ANALOG_TOPICS = {
  analogs_events_table: {
    title: 'Events table: seven El Ninos vs 2026-27',
    category: 'samui',
    aliases: ['events table', 'peak ONI', 'peak RONI', 'so far row', 'analog events', 'strong El Ninos'],
    short: 'One row per strong El Nino since 1982 (1982-83, 1987-88, 1991-92, 1997-98, 2009-10, 2015-16, 2023-24) with its peak ONI and RONI read from the NOAA CPC series, and a highlighted "so far" row for 2026-27.',
    body: `The table lists the El Ninos that NOAA's ONI table classes as strong or very strong since 1950, plus 1987-88 (listed as strong in older tables; the current ONI peaks at +1.49 °C, just under the band, and the page says so in a note).

Columns:

- **Peak ONI / Peak RONI**: the highest 3-month value between spring of the developing year and early summer of the next, with its season code (NDJ 1997 = November-December-January centred on December 1997). Both are read from the NOAA CPC files the app already collects ([[oni]], [[roni]]); nothing is typed in by hand.
- **Strength**: the [[strength_categories|NOAA band]] of the peak ONI.
- **ONI at JJA**: the value at the same stage the current event has reached (June-July-August of the developing year), for a like-for-like comparison.
- **Impacts**: how many documented reports the page holds for that event (see [[analogs_impacts]]).

The **2026-27 so far** row (highlighted) shows the current event's latest ONI, RONI and weekly Nino 3.4 with their dates, and the rain of the season under way. Its Samui columns fill in only when the months are complete: a blank means "not yet", never "nothing happened".`,
    howToRead: `Compare like with like: the "ONI at JJA" column is the fair comparison with 2026 (ONI +1.80 °C in JJA 2026 was above all seven analogs at that stage). The peak column says how big each event became by the winter, which 2026-27 has not reached yet.`,
    whyItMatters: 'It tells you which past dry seasons are the closest precedents for 2027, and how unusual the current event already is.',
    related: ['analogs', 'analogs_reading', 'oni', 'roni', 'strength_categories', 'past_events'],
    sources: [SRC_ANALOGS.oniTable, SRC.cpcIndices],
  },
  analogs_colour_scale: {
    title: 'Samui metrics table and its colours',
    category: 'samui',
    aliases: ['colour scale', 'color scale', 'rain % of normal colours', 'metrics table', 'neutral median', 'yardstick'],
    short: 'Rain is coloured by % of the 1991-2020 normal (orange under 75%, red under 60%, blue above 125%), heat by feels-like degrees and heat days, dry spells by length. The last row is the median of ENSO-neutral years, the yardstick.',
    body: `Each event's water year is reduced to six numbers for Koh Samui, all from the ERA5 grid cell that holds Maenam ([[era5]]):

- **Oct-Dec rain**: the northeast-monsoon refill, as % of the 1991-2020 normal of the same cell.
- **Jan-May rain**: the dry season after the El Nino peak.
- **Feb-Apr rain**: the danger window when the tanks are lowest.
- **Max feels-like**: the hottest daily maximum feels-like temperature in Jan-May, with its date.
- **Days >= 39 °C**: days in Jan-May with a feels-like maximum at or above 39 °C (the risk engine's heat "watch" threshold, see [[factor_heat]]).
- **Longest dry spell**: the longest run of days with less than 1 mm of rain in Jan-May, counted across month ends.

The **neutral median** row is the median of the same numbers over the water years whose ONI stayed between -0.5 and +0.5 °C from autumn to spring (no El Nino and no La Nina): what a "normal" year looks like in the same data. The count of years (n) is shown.`,
    thresholds: {
      columns: ['Colour', 'Rain (% of normal)', 'Meaning'],
      rows: [
        ['red', 'below 60%', 'serious deficit: the live water factor calls this "prepare"'],
        ['orange', '60% to 74%', 'deficit: the live water factor calls this "watch"'],
        ['plain', '75% to 125%', 'near normal'],
        ['blue', 'above 125%', 'wet: the monsoon over-delivered (floods possible)'],
      ],
      note: 'Heat cells go orange from 39 °C feels-like and red from 40 °C; heat days orange from 3, red from 7; dry spells orange from 30 days, red from 45. Thresholds match the live factors and the takeaways.',
    },
    howToRead: `Read down a column to compare events, and against the neutral row to see what is unusual. A cell shown as "--" with a "loading" note means a month of the ERA5 history is not stored yet; the number is not estimated.`,
    whyItMatters: 'The Feb-Apr column is the one to watch: in 6 of the 7 events it was under 60% of normal, and that is the window when Samui ran short of water in 2016 and 2024.',
    related: ['analogs_reading', 'analogs_events_table', 'rain_vs_normal', 'factor_water', 'factor_heat', 'heat_index'],
    sources: [SRC.omEra5, SRC_ANALOGS.wmoDry],
  },
  analogs_charts: {
    title: 'Monthly rain and heat charts (aligned by water year)',
    category: 'samui',
    aliases: ['monthly chart', 'aligned by month', 'normal band', 'water year chart', 'rain chart', 'heat chart'],
    short: 'Every event drawn on the same 12-month axis from June of the developing year to May of the next, with the 1991-2020 monthly normal as a band and 2026 as the thick line that stops at the last complete month.',
    body: `The horizontal axis is the island's water year: June to September (southwest monsoon, the event grows), October to December (northeast monsoon, the refill), January to May (the dry season after the peak). "Y" is the year the event started, "Y+1" the next one.

- **Rain chart**: monthly ERA5 rain in mm for each event; the shaded band is the 1991-2020 normal of the same month (the light band spans 75% to 125% of it). A line under the band in Oct-Dec means a weak refill; under it in Feb-Apr, a hard dry season.
- **Heat chart**: the hottest feels-like day of each month; the dashed line is the 1991-2020 normal of that monthly maximum. The 39 °C reference line is the risk engine's heat "watch" threshold.

Use the legend to hide or show events; hover or tap a month for every event's value. "Show table" gives the same numbers as text.`,
    howToRead: 'Look for where a line leaves the band and how long it stays out. The 2026 line only covers complete months (a month needs at least 25 valid days), so it ends before the newest partial month.',
    whyItMatters: 'The shape of the year matters more than one total: 2015-16 had a normal refill and still a very dry Feb-Apr; 1991-92 and 2009-10 were dry from October on.',
    related: ['analogs_reading', 'analogs_colour_scale', 'climatology_baseline', 'samui_seasons', 'heat_index'],
    sources: [SRC.omEra5, SRC_ANALOGS.chartsCls],
  },
  analogs_impacts: {
    title: 'Documented impacts timeline',
    category: 'samui',
    aliases: ['documented', 'impacts timeline', 'what happened', 'water rationing', 'verbatim quote', 'impact types', 'not found'],
    short: 'Dated reports of what happened on Samui, Koh Phangan, Koh Tao and the southern provinces around each event (rationing, floods, bleaching, haze, heat, papers), each with a verbatim quote and a link checked live on the date shown.',
    body: `"Documented" is a kind of information, next to "reanalysis" (ERA5 numbers) and "observed" (NOAA indices): it means a dated page says so. Every entry carries the sentence quoted from the page, the publisher, the publication date and the day the link was checked. Nothing is inferred from the numbers: a dry Feb-Apr in ERA5 does not create a "water shortage" entry; a newspaper report does.

Types: **water shortage** (rationing, trucks, PWA notices), **drought**, **flood**, **storm**, **haze**, **heat**, **bleaching** (coral), **paper** (peer-reviewed studies of the region).

Entries are tagged with the El Nino event they belong to. Reports from La Nina or neutral years (the March 2011 floods, December 2016 to January 2017, storm Pabuk in January 2019, December 2022, November-December 2024) are kept under "not an El Nino year" so the timeline also shows what the northeast monsoon does to the island whatever ENSO says.

The **"looked for, not found"** list says which reports were searched for and did not surface (for example a Samui water-shortage report for 1998 or 2019-20), so a gap in the timeline is not read as "nothing happened".`,
    howToRead: 'Filter by type or by event. The badge "documented" links to the source; the date is the event date as the report gives it (a year alone when the report only gives the year).',
    whyItMatters: 'Rain deficits become real through their consequences: in 2016 and 2024 Samui rationed water in the dry season after a strong El Nino. The timeline shows what those years looked like on the ground.',
    related: ['analogs', 'analogs_limits', 'samui_water_supply', 'factor_flood', 'coral_reef_watch', 'asmc_haze'],
    sources: [SRC_ANALOGS.bp2016, SRC.samuiWater],
  },
  analogs_history_status: {
    title: 'History loading state ("loading, not estimated")',
    category: 'samui',
    aliases: ['windows pending', 'history loading', 'complete false', 'decade windows', 'ERA5 history status'],
    short: 'The ERA5 history is fetched in decade windows, one per hour after start-up. Until every window is stored, the numbers that need a missing month are blank and labelled "loading, not estimated".',
    body: `The daily ERA5 data since 1950 (about 28,000 days) is downloaded in decade windows, one window per hourly run and never in the first five minutes after the server starts, so the shared Open-Meteo quota is respected. The status line at the top of the page says how many months are stored, which windows are still pending and the last day with valid data (ERA5 lags about five days).

While a window is pending:

- an event whose water year is not fully stored has "complete: false" and blank Samui numbers;
- the neutral baseline counts only complete years, so its n can be small;
- the takeaways say "No reconstructed event yet" instead of quoting partial numbers.

Nothing is estimated to fill the gap. Once the windows are in (about eight hours on a fresh install), the page is complete and only the current year is refreshed, once a day.`,
    howToRead: 'A green "complete" state with a recent ERA5 date is the normal case. "Loading" with a list of windows means come back later, or check the Sources page (source samui_era5_history).',
    whyItMatters: 'A blank cell is a promise: the page would rather show nothing than a number that was not computed from the data.',
    related: ['analogs_reading', 'freshness', 'sources_page', 'era5'],
    sources: [SRC.omEra5],
  },
} satisfies Record<string, TopicDef>
