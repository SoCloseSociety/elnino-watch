"""Alert dispatch for the Koh Samui watch.

When to alert (after each evaluation):
- the overall level ROSE compared with the previous evaluation (and is >= 1);
- any factor reached level >= 3;
- the overall level has been UNKNOWN (critical data missing) for more than 6 h
  ("data gap", once per day): missing data must never pass silently as "no alert".
Each alert is stored with a dedup_key `kind:level:day` (Bangkok day), so the same
situation is announced at most once a day. New alerts are delivered to:
- Telegram Bot API sendMessage, if settings.telegram_bot_token + telegram_chat_id;
- a webhook, POST {neo_api_url}/device_alert (Bearer neo_api_token), if set (docs/BOT_CONNECTOR.md).
Delivered channels (or `<channel>:error`) are recorded in alerts.delivered.
With no settings the alert is only stored and shown in the UI.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import httpx

from .. import db
from ..config import settings
from .collectors import today_bkk

log = logging.getLogger("elnino.local.alerts")
DATA_GAP_AFTER = timedelta(hours=6)


def plan_alerts(risk: dict, previous_level: int | None) -> list[dict]:
    """Pure: which alerts this evaluation should raise."""
    day = today_bkk().isoformat()
    out = []
    lvl = risk["level"]
    if lvl is None:
        gap = _data_gap(risk, day)
        if gap:
            out.append(gap)
    elif lvl >= 1 and (previous_level is None or lvl > previous_level):
        out.append({
            "kind": "local_level", "level": risk["level_key"],
            "title": f"Koh Samui: level {risk.get('level_label', risk['level_key'])}",
            "body": risk["headline"],
            "dedup_key": f"local_level:{risk['level_key']}:{day}",
        })
    for f in risk["factors"]:
        if f["level"] is not None and f["level"] >= 3:
            val = f.get("value_label") or (f"{f['value']} {f.get('unit_label') or f['unit'] or ''}"
                                           .strip() if f["value"] is not None else "")
            out.append({
                "kind": f"factor_{f['id']}", "level": f["level_key"],
                "title": f"Koh Samui: {f['label']} ({f['level_key']})",
                "body": f"{val}. {f['explanation']}".strip(". ")[:900],
                "dedup_key": f"factor_{f['id']}:{f['level']}:{day}",
            })
    return out


def _data_gap(risk: dict, day: str, now: datetime | None = None) -> dict | None:
    since = risk.get("unknown_since")
    if not since:
        return None
    t = datetime.fromisoformat(since)
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    now = now or datetime.now(UTC)
    if now - t < DATA_GAP_AFTER:
        return None
    missing = (risk.get("coverage") or {}).get("critical_missing") or []
    hours = int((now - t).total_seconds() // 3600)
    return {
        "kind": "data_gap", "level": "unknown",
        "title": "Koh Samui: risk level unknown (data gap)",
        "body": (f"No current data for {', '.join(missing) or 'critical factors'} for {hours} h. "
                 f"{risk.get('headline', '')} Check the TMD and the ferry operators directly.")[:900],
        "dedup_key": f"data_gap:{day}",
    }


def _text(a: dict) -> str:
    return f"{a['title']}\n{a['body']}"


async def _deliver(client: httpx.AsyncClient, a: dict) -> list[str]:
    done: list[str] = []
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            r = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": settings.telegram_chat_id, "text": _text(a)[:4000],
                      "disable_web_page_preview": True})
            r.raise_for_status()
            done.append("telegram")
        except httpx.HTTPError as e:
            log.warning("telegram delivery failed: %s", type(e).__name__)
            done.append("telegram:error")
    if settings.neo_api_url and settings.neo_api_token:
        try:
            r = await client.post(
                settings.neo_api_url.rstrip("/") + "/device_alert",
                headers={"Authorization": f"Bearer {settings.neo_api_token}"},
                json={"device": "elnino-watch", "kind": "elnino",
                      "highs": _text(a).replace("\n", " -- ")[:300]})
            r.raise_for_status()
            done.append("neo")
        except httpx.HTTPError as e:
            log.warning("neo delivery failed: %s", type(e).__name__)
            done.append("neo:error")
    return done


def _set_delivered(alert_id: int, channels: list[str]) -> None:
    with db._lock:
        c = db.conn()
        c.execute("UPDATE alerts SET delivered=? WHERE id=?", (json.dumps(channels), alert_id))
        c.commit()


async def dispatch(risk: dict, previous_level: int | None,
                   client: httpx.AsyncClient | None = None) -> list[dict]:
    """Store new alerts and deliver them. Returns the alerts actually created."""
    created = []
    planned = plan_alerts(risk, previous_level)
    if not planned:
        return created
    own = client is None
    client = client or httpx.AsyncClient(timeout=20.0,
                                         headers={"User-Agent": settings.user_agent})
    try:
        for a in planned:
            aid = db.add_alert(a["level"], a["kind"], a["title"], a["body"], a["dedup_key"])
            if aid is None:
                continue  # already raised today
            channels = await _deliver(client, a)
            _set_delivered(aid, channels)
            created.append(a | {"id": aid, "delivered": channels})
    finally:
        if own:
            await client.aclose()
    return created
