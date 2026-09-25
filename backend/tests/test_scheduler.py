"""Scheduler: independent per-collector tasks, timeouts, retry cadence."""

from __future__ import annotations

import asyncio

import pytest

from app import db, scheduler
from app.collectors.base import Collector


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


class Slow(Collector):
    name, title, category, provider = "t_slow", "slow", "news", "test"
    homepage = endpoint = "https://example.invalid"
    interval_s = 1

    async def collect(self, ctx):
        await asyncio.sleep(30)
        return 1


class Fast(Slow):
    name = "t_fast"

    async def collect(self, ctx):
        return db.upsert_observations(self.name, [{"series": "s", "ts": db.now_iso(),
                                                   "value": 1.0}])


async def test_slow_collector_does_not_block_fast_one(monkeypatch):
    monkeypatch.setattr(scheduler, "all_collectors", lambda: [Slow(), Fast()])
    monkeypatch.setattr(scheduler, "TICK_S", 0.05)
    monkeypatch.setattr(scheduler, "_maintenance_due", lambda: 3600.0)
    monkeypatch.setattr(scheduler, "next_delay", lambda c, r: 0.05)

    async def no_hooks():
        return None

    monkeypatch.setattr(scheduler, "run_hooks", no_hooks)
    task = asyncio.create_task(scheduler.loop())
    await asyncio.sleep(0.6)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    fast = db.query("SELECT COUNT(*) AS n FROM source_runs WHERE source='t_fast'")[0]["n"]
    slow = db.query("SELECT COUNT(*) AS n FROM source_runs WHERE source='t_slow'")[0]["n"]
    assert fast >= 3 and slow == 0  # the old batch gather would have waited on Slow


def test_next_delay_policy():
    c = type("C", (Slow,), {"interval_s": 6 * 3600})()
    assert scheduler.next_delay(c, {"ok": True}) == 6 * 3600
    assert scheduler.next_delay(c, {"ok": False, "error": "boom"}) == 30 * 60
    assert scheduler.next_delay(c, {"ok": False, "http_status": 429}) == 6 * 3600
    assert scheduler.next_delay(c, {"ok": False, "needs_config": ["x"]}) == 6 * 3600


def test_initial_delay_retries_failed_source_sooner():
    c = type("C", (Slow,), {"name": "t_six", "interval_s": 6 * 3600})()
    assert scheduler.initial_delay(c) == 0.0
    db.record_run("t_six", db.now_iso(), ok=False, error="ConnectError")
    assert 29 * 60 < scheduler.initial_delay(c) <= 30 * 60
    db.record_run("t_six", db.now_iso(), ok=True, items=1)
    assert scheduler.initial_delay(c) > 5 * 3600
