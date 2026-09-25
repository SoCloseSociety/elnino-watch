# Source and alert filters

id: filters_sources_alerts
short: List only some kinds of sources or states (for example "stale" or "error"), and only some alert levels, kinds or dates.

## What it is
The sources page can be filtered by category (ocean index, official, maritime,
disaster, news, social, local, ...) and by state (ok, stale, empty, error,
needs_config, pending). The alert history can be filtered by level, kind and date.

## How to read it
"state = stale,error" is the quick "what is not working right now" view. Alerts are
listed newest first.

## Why it matters for Koh Samui
When a decision is near, you want to know at a glance which data you can trust and
which alerts were already sent.

## Limits
A source's state reflects its last run only; a source that fails once and then
recovers shows ok again. The run history keeps the last 200 runs per source.

## Sources
- Freshness rules behind "stale": see the help topic source_freshness.
