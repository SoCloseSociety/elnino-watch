"""Re-check every curated social account against the live platform.

    cd backend && uv run python scripts/verify_accounts.py

For each entry of app.accounts.ACCOUNTS:
- bluesky : com.atproto.identity.resolveHandle + app.bsky.actor.getProfile +
            last post date (public AppView, keyless)
- x       : FxTwitter public profile API (keyless); falls back to the X API
            v2 users/by/username when X_BEARER_TOKEN is set
- telegram: t.me/s/<channel> preview (title + last message date)

An account passes when it exists, the returned display name still equals the
curated `name` (catches a handle that changed owner), the Bluesky handle
resolves to the same DID as the profile, and it posted in the last
STALE_DAYS days (a dormant account adds nothing to a live feed). Exit code 1
if any account fails, so this can run in CI or before editing the list.
"""

from __future__ import annotations

import asyncio
import re
import sys
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.accounts import ACCOUNTS
from app.config import settings

BSKY = "https://public.api.bsky.app/xrpc"
FX = "https://api.fxtwitter.com/2"
STALE_DAYS = 90
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def name_matches(expected: str, got: str) -> bool:
    if not expected:  # curated with an empty display name (Bluesky allows it)
        return True
    return _norm(expected) == _norm(got)


async def check_bluesky(c: httpx.AsyncClient, a: dict) -> dict:
    r = await c.get(f"{BSKY}/com.atproto.identity.resolveHandle", params={"handle": a["handle"]})
    if r.status_code != 200:
        return {"ok": False, "detail": f"resolveHandle {r.status_code}"}
    did = r.json().get("did", "")
    p = (await c.get(f"{BSKY}/app.bsky.actor.getProfile", params={"actor": a["handle"]})).json()
    if p.get("did") != did:  # the handle's DNS/well-known points elsewhere: ambiguous
        return {"ok": False, "detail": f"handle resolves to {did[:20]}, profile is "
                                       f"{str(p.get('did'))[:20]}"}
    f = (await c.get(f"{BSKY}/app.bsky.feed.getAuthorFeed",
                     params={"actor": did, "limit": 5, "filter": "posts_no_replies"})).json()
    last = max((i["post"]["record"].get("createdAt", "") for i in f.get("feed", [])), default="")
    got = p.get("displayName") or ""
    return {"ok": name_matches(a.get("name", ""), got), "got": got,
            "followers": p.get("followersCount"), "last": last[:10], "detail": did[:24]}


async def check_x(c: httpx.AsyncClient, a: dict) -> dict:
    r = await c.get(f"{FX}/profile/{a['handle']}", headers={"User-Agent": BROWSER_UA})
    if r.status_code == 200 and r.json().get("user"):
        u = r.json()["user"]
        s = await c.get(f"{FX}/profile/{a['handle']}/statuses",
                        headers={"User-Agent": BROWSER_UA})
        last = ""
        if s.status_code == 200:
            ts = [t.get("created_timestamp") or 0 for t in s.json().get("results", [])
                  if (t.get("author") or {}).get("screen_name", "").lower()
                  == a["handle"].lower()]
            if ts:
                last = datetime.fromtimestamp(max(ts), UTC).date().isoformat()
        got = u.get("name") or ""
        return {"ok": name_matches(a.get("name", ""), got), "got": got,
                "followers": u.get("followers"), "last": last, "detail": "fxtwitter"}
    if settings.x_bearer_token:
        r2 = await c.get(f"https://api.x.com/2/users/by/username/{a['handle']}",
                         headers={"Authorization": f"Bearer {settings.x_bearer_token}"})
        if r2.status_code == 200 and "data" in r2.json():
            got = r2.json()["data"].get("name", "")
            return {"ok": name_matches(a.get("name", ""), got), "got": got, "followers": None,
                    "last": "", "detail": "x api v2"}
    return {"ok": False, "detail": f"fxtwitter {r.status_code}"}


async def check_telegram(c: httpx.AsyncClient, a: dict) -> dict:
    r = await c.get(f"https://t.me/s/{a['handle']}", headers={"User-Agent": BROWSER_UA})
    if r.status_code != 200:
        return {"ok": False, "detail": f"t.me/s {r.status_code} (not a public channel?)"}
    t = re.search(r'<meta property="og:title" content="([^"]*)"', r.text)
    subs = re.search(r'<span class="counter_value">([^<]+)</span> <span class="counter_type">'
                     r'subscribers', r.text)
    times = re.findall(r'<time[^>]+datetime="([^"]+)"', r.text)
    got = t.group(1) if t else ""
    return {"ok": bool(times) and name_matches(a.get("name", ""), got), "got": got,
            "followers": subs.group(1) if subs else None,
            "last": times[-1][:10] if times else "", "detail": "t.me/s"}


CHECKS = {"bluesky": check_bluesky, "x": check_x, "telegram": check_telegram}


async def main() -> int:
    rows = []
    async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                 headers={"User-Agent": settings.user_agent}) as c:
        for a in ACCOUNTS:
            try:
                res = await CHECKS[a["platform"]](c, a)
            except (httpx.HTTPError, ValueError, KeyError) as e:
                res = {"ok": False, "detail": f"{type(e).__name__}: {e}"[:60]}
            rows.append((a, res))
            await asyncio.sleep(0.6 if a["platform"] == "x" else 0.2)
    hdr = f"{'state':5} {'platform':8} {'handle':30} {'kind':9} {'display name (live)':38} " \
          f"{'followers':>9} {'last post':10}"
    print(hdr)
    print("-" * len(hdr))
    bad = 0
    cutoff = (datetime.now(UTC) - timedelta(days=STALE_DAYS)).date().isoformat()
    for a, r in rows:
        state = "OK" if r["ok"] else "FAIL"
        if r["ok"] and (r.get("last") or "") < cutoff:
            state = "STALE"
        bad += state != "OK"
        print(f"{state:5} {a['platform']:8} {a['handle'][:30]:30} "
              f"{a['kind']:9} {str(r.get('got', r.get('detail')))[:38]:38} "
              f"{r.get('followers') or ''!s:>9} {r.get('last', ''):10}")
    print(f"\n{len(rows) - bad}/{len(rows)} verified")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
