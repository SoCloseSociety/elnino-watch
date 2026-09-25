"""Run every collector against the REAL sources and print a health + freshness table.

    cd backend && uv run python scripts/verify_sources.py            # all, scratch DB
    cd backend && uv run python scripts/verify_sources.py cpc_oni gdacs
    cd backend && uv run python scripts/verify_sources.py --live-db  # write into data/elnino.db
    cd backend && uv run python scripts/verify_sources.py --json

This is the one thing in the repo that hits reality on purpose (CLAUDE.md rule 7).
By default it writes into a throw-away SQLite file, so the freshness column shows
exactly what each source serves RIGHT NOW (not what an older run left in the DB),
and a running service is not disturbed. Each run gets the same per-run timeout
as the scheduler (min(interval, 300 s)).

Exit code: 0 if every source is ok / empty / needs_config, 1 if any is error or stale.
A stale source whose collector declares `expected_stale` (a documented silent feed, e.g.
climategov_enso_blog) is printed with its reason and does NOT set the exit code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.collectors import all_collectors, source_state
from app.collectors.base import run_collector
from app.scheduler import MAX_PARALLEL, make_client


def failing(rows: list[dict]) -> list[dict]:
    """Rows that make the run fail: errors, and stale sources that are not documented as
    silent (`expected_stale`)."""
    return [r for r in rows if r["state"] == "error"
            or (r["state"] == "stale" and not r.get("expected_stale"))]


def _dur(s: int | None) -> str:
    if s is None:
        return "-"
    if s >= 86400:
        return f"{s / 86400:.1f}d"
    if s >= 3600:
        return f"{s / 3600:.1f}h"
    return f"{s // 60}m"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="collector names (default: all)")
    ap.add_argument("--live-db", action="store_true", help="write into the configured DB")
    ap.add_argument("--json", action="store_true", help="print JSON rows instead of a table")
    args = ap.parse_args()

    if not args.live_db:
        tmp = Path(tempfile.mkdtemp(prefix="elnino-verify-")) / "verify.db"
        db.use_path(tmp)
    cols = [c for c in all_collectors() if not args.names or c.name in args.names]
    unknown = set(args.names) - {c.name for c in cols}
    if unknown:
        print(f"unknown collector(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    t0 = time.monotonic()
    sem = asyncio.Semaphore(MAX_PARALLEL)
    async with make_client() as client:

        async def one(c):
            async with sem:
                return await run_collector(c, client)

        await asyncio.gather(*(one(c) for c in cols))
    rows = [source_state(c) for c in cols]

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        hdr = (f"{'source':26} {'state':12} {'items':>6} {'http':>4} {'secs':>6}  "
               f"{'newest data':25} {'age':>6} {'max':>6}  note")
        print(hdr)
        print("-" * len(hdr))
        for r in sorted(rows, key=lambda r: (r["category"], r["name"])):
            last = r["last_run"] or {}
            f = r["freshness"]
            note = (last.get("error") or "")[:70]
            if not note and r["state"] == "stale":
                note = f"data older than {_dur(f['max_age_s'])} ({f['basis']})"
                if r.get("expected_stale"):
                    note += f"; expected: {r['expected_stale']}"
            secs = f"{(last.get('latency_ms') or 0) / 1000:.1f}" if last.get("latency_ms") else "-"
            print(f"{r['name']:26} {r['state']:12} {last.get('items') or 0:>6} "
                  f"{last.get('http_status') or '-':>4} {secs:>6}  "
                  f"{(f['newest_data_at'] or '-')[:25]:25} {_dur(f['age_s']):>6} "
                  f"{_dur(f['max_age_s']):>6}  {note}")
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["state"]] = counts.get(r["state"], 0) + 1
        expected = [r["name"] for r in rows if r["state"] == "stale" and r.get("expected_stale")]
        print(f"\n{len(rows)} sources in {time.monotonic() - t0:.0f} s: "
              + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
              + (f" (stale but expected: {', '.join(expected)})" if expected else ""))
        if not args.live_db:
            print(f"(scratch DB: {tmp})")
    return 1 if failing(rows) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
