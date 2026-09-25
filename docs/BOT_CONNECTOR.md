# Bot / assistant connector

Four read-only calls are enough for an assistant, a chat bot or a home-automation hub to
answer *"how is the El Nino going, and is Koh Samui OK?"*. The full API (`/api/series`,
`/api/feed`, `/api/events`, `/api/sources`, ...; contract in [AGENTS.md](../AGENTS.md)) stays
available, but it is built for the dashboard: this document only describes what is useful
to a bot.

Base URL: your instance, e.g. `http://127.0.0.1:8911` for a local install (localhost only,
no auth: anything that can reach the port can read it; all data is public-source and the
bot never writes) or `https://elnino.example.com` for a public-mode deployment (reads need
no token; writes need `X-Admin-Token`).

The other direction: when the island level rises, the tracker can push an alert to your
bot, `POST {NEO_API_URL}/device_alert` with `Authorization: Bearer {NEO_API_TOKEN}` and a
JSON body `{device: "elnino-watch", kind: "elnino", level, title, body, created_at}`, if
those two variables are set in the tracker's `.env` (see `backend/app/local/alerts.py`).

## 1. The briefing (start here)

`GET /api/briefing`

```json
{ "generated_at": "2026-09-24T13:55:35+00:00", "method": "rules", "model": null,
  "headline": "Strong El Nino (ONI +1.80 degC, JJA 2026); Koh Samui: PREPARE.",
  "local_level": 2, "local_level_key": "prepare",
  "sections": [{ "id": "enso", "title": "ENSO state",
                 "bullets": ["NOAA CPC status: El Niño Advisory (issued 2026-09-10; next update 2026-10-08).", "..."],
                 "sources": [{ "title": "NOAA CPC ENSO Diagnostic Discussion", "url": "https://..." }] }],
  "text": "Strong El Nino ... \n\nENSO state:\n- ..." }
```

Sections, in order: `enso`, `forecast`, `local`, `hazards` (within the home radius + GDACS
orange/red worldwide), `official` (5 latest bulletins), `gaps` (failing / stale /
unconfigured sources). `text` is ready to send as a chat message.

- `method: "rules"`: assembled by fixed rules from stored data, every number with its
  date. `method: "llm"`: the same facts rewritten by a model; any text with a number not
  present in the rules version is rejected (`llm_error` says why).
- Rebuilt every 6 h and whenever the island level changes. `POST /api/briefing/refresh`
  forces a rebuild (admin token in public mode).

## 2. Koh Samui risk level

`GET /api/local`

`level` 0..4 (`level_key`: normal | vigilance | prepare | act | leave), `headline`,
`evaluated_at`, `factors` (each: `value`, `unit_label`, `threshold`, `explanation`, `kind`,
`valid_for`, `source`, `url`, `as_of`), `actions` (what to do now), `triggers` (what would
raise the level), `coverage` (`missing`, `stale`, `critical_missing`).

**`level: null` / `level_key: "unknown"` means critical data is missing: never report that
as "all clear".** `GET /api/local/exit` gives the leave-the-island view (ferry / air routes,
7-day sea windows, checklist).

## 3. Latest index values

`GET /api/latest` -> `[{source, series, ts, value, unit, unit_label, kind, valid_for,
prev_value}]`, the latest OBSERVED point of every series (forecast rows are excluded).
Useful series: `oni` (official, 3-month, `ts` = centre month's 15th), `roni`,
`nino34_weekly_anom`, `nino34_daily_anom`, `soi`, `mei_v2`, `world_sst_anom`. Always quote
`ts` (or `valid_for`) with the value: ONI lags by about two months by design.

## 4. Alerts already raised

`GET /api/alerts?since=2026-09-01&level=act,leave&limit=20` -> newest first:
`{id, created_at, level, kind, title, body, dedup_key, delivered}`. Filters: `level`,
`kind` (comma lists), `since` (ISO), `limit` (<= 1000).

## 5. Tool definitions (for an LLM agent)

```python
{
    "name": "elnino_briefing",
    "description": (
        "Current El Nino situation and the Koh Samui risk level as a ready-to-send "
        "English briefing (ENSO state with dates, forecast probabilities, island level "
        "and top factors, nearby hazards, latest official bulletins, data gaps). Use for "
        "any question about El Nino, ENSO or safety on Koh Samui."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "refresh": {"type": "boolean", "default": False,
                        "description": "rebuild now instead of the stored (<= 6 h) one"},
        },
    },
}

{
    "name": "elnino_samui_level",
    "description": (
        "Koh Samui risk level (normal/vigilance/prepare/act/leave or unknown) with every "
        "factor's value, threshold, explanation and source, the actions for the current "
        "level and what would raise it. 'unknown' means missing data, not safety."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "exit_plan": {"type": "boolean", "default": False,
                          "description": "also return the leave-the-island view"},
        },
    },
}

{
    "name": "elnino_latest_values",
    "description": (
        "Latest observed values of ENSO indices and ocean series (ONI, RONI, weekly and "
        "daily Nino 3.4 anomaly, SOI, MEI, world SST anomaly), each with its date and "
        "the previous value."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "series": {"type": "array", "items": {"type": "string"},
                       "description": "series names to keep, e.g. ['oni', 'nino34_weekly_anom']; empty = all"},
        },
    },
}

{
    "name": "elnino_alerts",
    "description": "Alerts the tracker already raised for Koh Samui, newest first.",
    "input_schema": {
        "type": "object",
        "properties": {
            "since": {"type": "string", "description": "ISO date"},
            "level": {"type": "string", "description": "comma list, e.g. 'act,leave'"},
            "limit": {"type": "integer", "default": 10},
        },
    },
}
```

Mapping: `elnino_briefing` -> `GET /api/briefing` (or `POST /api/briefing/refresh`
when `refresh`); `elnino_samui_level` -> `GET /api/local` (+ `GET /api/local/exit`);
`elnino_latest_values` -> `GET /api/latest` filtered client-side; `elnino_alerts` ->
`GET /api/alerts`.

## Guard-rails

- **Read-only.** A bot must not call `POST /api/sources/verify` or `/run` from a chat:
  they hit every upstream source at once (GDELT rate-limits at 1 request / 5 s and
  answers 429 for a while after). In public mode those routes need the admin token anyway.
- **Quote dates and sources.** Every number has a timestamp; ONI and other monthly
  indices are weeks old by design. If `gaps` lists a stale or failing source, say so.
- **Never turn "unknown" into "safe".** Missing data is reported as missing.
- **English only** in what the bot relays from here, except third-party titles (news,
  posts), which stay in their original language.
