# Contributing to El Nino Watch

Thanks for helping. This project tracks a real climate event and its impact on a real
island; a wrong number can lead to a bad real-world decision, so the rules below are
stricter than in a typical dashboard. They are short.

## Ground rules

1. **Never fabricate data.** Everything shown comes from a real response. No placeholder
   numbers, no mock posts, no invented social handles. A social account goes in the
   curated list only after its handle was resolved against the live platform API (and the
   check is kept as a test or a script).
2. **No silent failure.** Every collector records a run. A missing credential is
   `needs_config`, a changed format is `SourceChanged`, an empty answer is `empty`, and all
   of them are visible on the Sources page.
3. **Freshness is part of the data.** Every value carries its timestamp and source link.
   Stale sources are marked as stale, never hidden.
4. **Respect the providers.** A collector's `interval_s` matches how often the source
   really updates. Identify with `settings.user_agent`. Follow rate limits (GDELT: one
   request every 5 s). Store titles and links, not full articles.
5. **Free and keyless first.** Paid or credentialed sources are optional and degrade to
   `needs_config`.
6. **Risk levels are explainable.** Every factor ships with its value, threshold,
   explanation, source and link. No black-box score.
7. **Tests never hit the network.** Use `respx` fixtures made from real captured payloads
   (`backend/tests/fixtures/`). `backend/scripts/verify_sources.py` is the one thing that
   hits reality, on purpose, when you run it.
8. **No em dashes** in code, docs or UI text (use `--`). The frontend build fails on one in
   the Learn content.
9. **English only** for user-facing text. Third-party content (news titles, posts) stays in
   its original language.
10. **Nothing ships without its explanation.** Every new source, series, status, map layer,
    factor, filter or page comes with a help topic: what it is, how to read it (units,
    colours, thresholds), why it matters, its limits, and 1-3 checked links. Topics live in
    `frontend/src/help/topics/*.ts` (see `frontend/src/help/README.md`); backend-only
    changes can drop a Markdown file in `backend/docs/help_topics/<id>.md`, which
    `npm run help:import` merges.
11. **Cameras: public feeds only.** Only webcams their owner publishes for public viewing.

The full agent / developer guide, with the API contract, is in [AGENTS.md](AGENTS.md).

## Set up

```bash
# backend (Python 3.12+, uv)
cd backend && uv sync && uv run pytest -q && uv run ruff check app scripts tests

# frontend (Node 22+)
cd frontend && npm ci && npm run build      # or npm run dev (port 5211, proxies /api)

# run everything on http://127.0.0.1:8911
./start.sh
```

## Adding a data source

1. Read `backend/app/collectors/base.py` first: it is the whole contract (`name`, `title`,
   `category`, `provider`, `homepage`, `interval_s`, `max_age_s`, `freshness_basis`,
   `needs`, `collect()`).
2. Fetch the real thing once, save the payload under `backend/tests/fixtures/<domain>/`,
   and write the parser against it. Add a `respx` test that asserts values, units and
   dates.
3. Register the class in the module's `COLLECTORS` list.
4. Add the help topic (rule 10) and, if the source feeds a chart, its unit and kind
   (`observed`, `forecast`, `model_analysis`, `reanalysis`, `bulletin`; see
   `backend/app/local/provenance.py`).
5. Run `uv run python scripts/verify_sources.py` once to see it go live, then add the row
   to `docs/DATA_SOURCES.md` (or regenerate it from the registry).

Prefer an issue first for a new source: use the "Data source request" template so we can
check the provider's terms and update frequency together.

## Pull requests

- One topic per PR. Keep the diff readable.
- `uv run pytest -q`, `uv run ruff check app scripts tests` and `npm run build` must pass
  (CI runs them).
- Describe what changed for a visitor and what changed for the data (a new value, a
  changed threshold, a changed period), with the upstream link you checked.
- If a threshold or rule of the risk engine changes, explain why in the PR and update the
  help topic that documents it.

## Reporting a wrong number

That is the most valuable issue you can open. Use the bug template and give: the page, the
value shown, the value at the source (with its URL and time), and a screenshot if you
have one.
