import httpx
import pytest

from app import db
from app.collectors.base import Collector, NeedsConfig, run_collector


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


class Ok(Collector):
    name, title, category, provider = "t_ok", "ok", "ocean_index", "test"
    homepage = endpoint = "https://example.invalid"
    interval_s = 60

    async def collect(self, ctx):
        return db.upsert_observations(self.name, [{"series": "s", "ts": "2026-01-15", "value": 1.0}])


class Boom(Ok):
    name = "t_boom"

    async def collect(self, ctx):
        raise ValueError("format moved")


class Cfg(Ok):
    name = "t_cfg"
    needs = ("x_bearer_token",)


class CfgRaise(Ok):
    name = "t_cfg2"

    async def collect(self, ctx):
        raise NeedsConfig("x_auth_token")


async def test_every_outcome_is_recorded():
    async with httpx.AsyncClient() as c:
        assert (await run_collector(Ok(), c))["ok"]
        assert not (await run_collector(Boom(), c))["ok"]
        assert "needs_config" in await run_collector(Cfg(), c)
        assert "needs_config" in await run_collector(CfgRaise(), c)
    runs = {r["source"]: r for r in db.query("SELECT * FROM source_runs")}
    assert runs["t_ok"]["ok"] == 1 and runs["t_ok"]["items"] == 1
    assert "format moved" in runs["t_boom"]["error"]
    assert runs["t_cfg"]["error"].startswith("needs_config")
    assert runs["t_cfg2"]["error"].startswith("needs_config")


def test_upsert_is_idempotent_and_replace_drops_closed():
    db.upsert_observations("s", [{"series": "a", "ts": "2026-01-01", "value": 1}])
    db.upsert_observations("s", [{"series": "a", "ts": "2026-01-01", "value": 2}])
    assert db.query("SELECT value FROM observations") == [{"value": 2.0}]
    db.replace_events("g", [{"ext_id": "1", "category": "flood", "lat": 0, "lon": 0}])
    db.replace_events("g", [{"ext_id": "2", "category": "flood", "lat": 0, "lon": 0}])
    assert [r["ext_id"] for r in db.query("SELECT ext_id FROM events")] == ["2"]


def test_alert_dedup():
    assert db.add_alert("act", "local", "t", "b", "k1")
    assert db.add_alert("act", "local", "t", "b", "k1") is None
