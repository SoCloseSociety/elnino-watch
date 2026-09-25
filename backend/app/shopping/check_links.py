"""Manual maintenance: open every link the shopping panel ships and report the HTTP status.

    cd backend && uv run python -m app.shopping.check_links

Hits the network on purpose (like scripts/verify_sources.py); never run by the app or
the tests. One request per URL, 4 at a time, with a browser User-Agent (the retail
sites answer unknown agents with a block page). It checks links only: re-pricing
stays a manual step (see docs/SHOPPING.md), because scraping Lazada / Shopee is
against their terms.
"""

from __future__ import annotations

import concurrent.futures as cf
import sys

import httpx

from . import catalog, offers

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126 Safari/537.36")


def all_urls() -> list[str]:
    data = offers.offers()
    urls: set[str] = set(catalog.REFERENCES.values())
    for it in data["items"].values():
        for li in it.get("listings", []):
            urls.add(li["url"])
        for comp in it.get("components", []):
            urls.update(li["url"] for li in comp["listings"])
        urls.update(x["url"] for x in it.get("search_links", []))
        for s in it.get("local_stores", []):
            urls.add(s["maps_url"])
            if s.get("source"):
                urls.add(s["source"])
    for s in data["stores"]:
        urls.update([s["maps_url"], s["source"]])
    return sorted(urls)


def check(url: str) -> tuple[str, str]:
    try:
        r = httpx.get(url, headers={"User-Agent": BROWSER_UA}, follow_redirects=True,
                      timeout=40)
        return str(r.status_code), url
    except httpx.HTTPError as e:
        return f"ERR {type(e).__name__}", url


def main() -> int:
    urls = all_urls()
    bad = 0
    with cf.ThreadPoolExecutor(4) as ex:
        for code, url in ex.map(check, urls):
            if code != "200":
                bad += 1
                print(code, url)
    print(f"{len(urls)} links checked, {bad} not 200")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
