"""Pull leads from the sites the GitHub Action discovered.

The Action commits sources/discovered_sites.json; this is the half that
turns those domains into actual leads, and it runs on the Mac because
that's where the database is.

Credit cost is the design constraint. Every site costs a search plus a
handful of scrapes, so sweeping all of them daily would scale Firecrawl
spend with a list that only ever grows. Instead each daily pass takes a
bounded, rotating slice — the whole list still gets covered, just over
several days rather than all at once, which is the right trade for a feed
nobody reads more than daily anyway.
"""

import json
import logging
from datetime import date
from pathlib import Path

from ..config import BACKEND_DIR
from .jobs import firecrawl_job_search

logger = logging.getLogger("bureau.sources.discovered")

SITES_PATH = BACKEND_DIR.parent / "sources" / "discovered_sites.json"

SITES_PER_PASS = 8
PAGES_PER_SITE = 3


def load_sites(kind: str = "job") -> list[dict]:
    if not SITES_PATH.exists():
        return []
    try:
        data = json.loads(SITES_PATH.read_text())
    except json.JSONDecodeError:
        logger.warning("discovered_sites.json is unparseable; ignoring it")
        return []
    return [s for s in data.get("sites", []) if s.get("type") == kind and s.get("domain")]


def todays_slice(sites: list[dict], per_pass: int = SITES_PER_PASS) -> list[dict]:
    """A deterministic rotating window keyed on the date — no cursor to
    persist, and the same day always picks the same sites, so a restart
    mid-pass doesn't reshuffle the world."""
    if not sites:
        return []
    ordered = sorted(sites, key=lambda s: s["domain"])
    start = (date.today().toordinal() * per_pass) % len(ordered)
    doubled = ordered + ordered
    return doubled[start : start + per_pass]


def fetch(role: str = "", per_pass: int = SITES_PER_PASS) -> list[dict]:
    """Searches today's slice of discovered job sites. `role` narrows the
    search when given; blank casts the widest net the site supports."""
    sites = todays_slice(load_sites("job"), per_pass)
    if not sites:
        return []

    out: list[dict] = []
    for site in sites:
        domain, region = site["domain"], site.get("region", "")
        query = f"{role} jobs {region}".strip() if role else f"jobs hiring {region}".strip()
        try:
            leads = firecrawl_job_search.fetch_scoped(
                query=query, region=region, domains=[domain], max_pages=PAGES_PER_SITE
            )
        except Exception:
            logger.exception("discovered-site sweep failed for %s", domain)
            continue
        logger.info("discovered site %s (%s): %d leads", domain, region, len(leads))
        out.extend(leads)
    return out
