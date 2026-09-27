#!/usr/bin/env python3
"""Find job-board and business-opportunity sites worldwide, and keep a
version-controlled list of them.

This is the half of the daily automation that runs on GitHub rather than on
the Mac, because it's the half that doesn't need anything local: it only
needs a web search and somewhere to commit a JSON file. The other half —
actually pulling leads from these sites — stays on the Mac, because that's
where the database and the local models are.

Search is DuckDuckGo via ddgs: free, no API key, and therefore nothing to
store as a repository secret.

The output (sources/discovered_sites.json) is deliberately a curated list
rather than a scrape dump: Bureau uses each entry's domain to scope its own
daily sweep, so a wrong or dead domain wastes a fetch and a model call every
day until someone removes it. Entries are therefore only added, never
silently replaced, and each carries where it came from.

Usage:
    python3 backend/scripts/discover_sources.py            # all regions
    python3 backend/scripts/discover_sources.py --regions "India,UAE"
    python3 backend/scripts/discover_sources.py --dry-run
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = REPO_ROOT / "sources" / "discovered_sites.json"

# Regions worth sweeping. Deliberately weighted toward the places the three
# keyless job APIs don't reach — they're remote-tech and Europe heavy, so
# sweeping Germany again adds little.
DEFAULT_REGIONS = [
    "United Arab Emirates", "Saudi Arabia", "Qatar", "Singapore", "India",
    "Japan", "South Korea", "Indonesia", "Vietnam", "Nigeria", "Kenya",
    "South Africa", "Egypt", "Brazil", "Mexico", "Argentina", "Australia",
    "Canada", "United Kingdom", "Germany",
]

QUERY_TEMPLATES = {
    "job": [
        "best job boards in {region} for professionals",
        "{region} recruitment website list hiring portal",
    ],
    "business": [
        "{region} business tenders and procurement opportunities portal",
        "{region} startup funding news and company directory",
    ],
}

# Aggregators, our own sources, and social sites are noise here: they're
# either already ingested or aren't lead sources at all.
EXCLUDED_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "reddit.com", "wikipedia.org", "quora.com", "medium.com",
    "remotive.com", "arbeitnow.com", "remoteok.com", "github.com",
    # Search engines turn up in their own results and are not lead sources.
    "google.com", "bing.com", "duckduckgo.com", "yahoo.com", "baidu.com",
}


def normalise_domain(url: str) -> str | None:
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if not host or "." not in host:
        return None
    if any(host == bad or host.endswith("." + bad) for bad in EXCLUDED_DOMAINS):
        return None
    if not re.fullmatch(r"[a-z0-9.-]+", host):
        return None
    return host


def load_existing() -> dict:
    if OUTPUT_PATH.exists():
        try:
            return json.loads(OUTPUT_PATH.read_text())
        except json.JSONDecodeError:
            print("existing file is unparseable; starting fresh", file=sys.stderr)
    return {"updated_at": None, "sites": []}


def _search_with_retry(query: str, limit: int, attempts: int = 3) -> list[dict]:
    """DuckDuckGo answers a perfectly good query with "No results found" when
    it's throttling, which silently costs a whole region's coverage."""
    from ddgs import DDGS

    for attempt in range(attempts):
        try:
            rows = list(DDGS().text(query, max_results=limit))
            if rows:
                return rows
        except Exception as exc:
            if attempt == attempts - 1:
                print(f"  search failed ({query}): {exc}", file=sys.stderr)
                return []
        time.sleep(3 * (attempt + 1))
    return []


def discover(region: str, kind: str, limit: int) -> list[dict]:
    found: list[dict] = []
    for template in QUERY_TEMPLATES[kind]:
        query = template.format(region=region)
        rows = _search_with_retry(query, limit)
        if not rows:
            print(f"  search returned nothing: {query}", file=sys.stderr)
            continue

        for item in rows:
            url = item.get("href") or item.get("url")
            title = item.get("title")
            domain = normalise_domain(url or "")
            if not domain:
                continue
            found.append({
                "name": (title or domain)[:120],
                "domain": domain,
                "region": region,
                "type": kind,
                "found_via": query,
            })
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regions", help="Comma-separated region list (default: a built-in sweep)")
    parser.add_argument("--limit", type=int, default=5, help="Results per query")
    parser.add_argument("--dry-run", action="store_true", help="Print what would change, write nothing")
    args = parser.parse_args()

    regions = [r.strip() for r in args.regions.split(",")] if args.regions else DEFAULT_REGIONS

    existing = load_existing()
    known = {site["domain"] for site in existing.get("sites", [])}
    added: list[dict] = []

    for region in regions:
        for kind in ("job", "business"):
            for site in discover(region, kind, args.limit):
                if site["domain"] in known:
                    continue
                known.add(site["domain"])
                site["first_seen"] = datetime.now(timezone.utc).date().isoformat()
                added.append(site)
                print(f"  + {site['domain']:38} {region} ({kind})")

    if not added:
        print("no new sites found")
        return 0

    print(f"\n{len(added)} new site(s)")
    if args.dry_run:
        return 0

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sites": sorted(existing.get("sites", []) + added, key=lambda s: (s["type"], s["region"], s["domain"])),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(payload['sites'])} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
