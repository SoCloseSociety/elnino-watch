"""Koh Samui personal watch: local collectors, risk engine, alerts, preparedness.

Importing this package registers the post-run hook: after each scheduler round
the risk engine re-evaluates and new alerts are dispatched.
"""

from __future__ import annotations

from .. import db
from ..scheduler import register_post_hook


async def evaluate_and_alert() -> dict:
    from . import alerts, risk

    prev = db.get_status("local_risk")
    prev_level = None
    if prev:
        # after an 'unknown' spell, compare with the last known floor so that data
        # coming back does not re-announce a level that never changed
        pv = prev["value"]
        prev_level = pv.get("level") if pv.get("level") is not None else pv.get("level_floor")
    result = risk.evaluate(save=True)
    result["alerts_created"] = await alerts.dispatch(result, prev_level)
    return result


async def _post_hook() -> None:
    await evaluate_and_alert()


register_post_hook(_post_hook)
