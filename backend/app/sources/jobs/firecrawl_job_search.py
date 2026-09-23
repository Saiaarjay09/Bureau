"""Firecrawl-based general job search: given a role and/or region,
searches the web for matching postings and extracts structured listings
from each matched page.

This is the source that reaches what the three keyless job boards
structurally can't: leadership/executive titles (Remotive/Arbeitnow/
RemoteOK skew toward individual-contributor tech roles, rarely "Director"
or "Head of") and non-Western regions (Remotive/RemoteOK are remote-only
and Arbeitnow is Europe-centric — none has meaningful Gulf/Middle East,
and Adzuna, the other free-tier option, doesn't cover the Middle East
either). Manual-only, like the other two Firecrawl sources, since it
spends credits per call."""

import logging
from datetime import datetime

from ...enrichment import guess_seniority
from ..concurrency import parallel_map
from ..firecrawl_client import get_client
from ..location import parse_location

logger = logging.getLogger("bureau.sources.firecrawl_jobs")

JOB_LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "remote_type": {"type": "string", "description": "remote, hybrid, or onsite if stated"},
                    "url": {"type": "string"},
                },
                "required": ["title", "company"],
            },
        }
    },
    "required": ["jobs"],
}

QUERY_TEMPLATES = [
    "{role} jobs in {region}",
    "{role} job openings {region} hiring now",
    "{role} vacancy {region}",
]


def _result_url(item) -> str | None:
    if isinstance(item, dict):
        return item.get("url")
    return getattr(item, "url", None)


def _search_one(client, query: str, limit_per_query: int) -> list[str]:
    try:
        result = client.search(query, limit=limit_per_query, sources=["web"])
    except Exception:
        logger.exception("Firecrawl search failed for %r", query)
        return []
    return [url for item in (getattr(result, "web", None) or []) if (url := _result_url(item))]


def _search_urls(client, role: str, region: str, limit_per_query: int = 5) -> list[str]:
    queries = [t.format(role=role, region=region or "").strip() for t in QUERY_TEMPLATES]
    results = parallel_map(lambda q: _search_one(client, q, limit_per_query), queries)
    urls = [url for batch in results if batch for url in batch]
    return list(dict.fromkeys(urls))  # dedupe, keep first-seen order


def _scrape_one(client, role: str, region: str, url: str) -> list[dict]:
    try:
        doc = client.scrape(
            url,
            formats=[{
                "type": "json",
                "prompt": (
                    f"Extract every current job listing on this page matching "
                    f"the role '{role}'" + (f" in {region}" if region else "")
                    + ": title, company, location, whether it's remote/hybrid/"
                    "onsite if stated, and the direct URL to the listing if present."
                ),
                "schema": JOB_LISTING_SCHEMA,
            }],
            only_main_content=True,
        )
    except Exception:
        logger.exception("Firecrawl scrape failed for %s", url)
        return []

    data = getattr(doc, "json", None) or {}
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    out = []
    for job in jobs:
        title = (job.get("title") or "").strip()
        company = (job.get("company") or "").strip()
        if not title or not company:
            continue
        # Fall back to the searched region when a listing doesn't state its
        # own location — the search itself was already scoped to it.
        continent, country, city = parse_location(job.get("location") or region)
        remote_type = (job.get("remote_type") or "").strip().lower() or None
        if remote_type not in ("remote", "hybrid", "onsite"):
            remote_type = None
        out.append({
            "lead_type": "job",
            "source": "firecrawl_jobs",
            "external_id": f"{url}:{title}:{company}".lower().replace(" ", "-")[:200],
            "title": title,
            "company": company,
            "company_domain": None,
            "url": job.get("url") or url,
            "continent": continent,
            "country": country,
            "city": city,
            "remote_type": remote_type,
            "seniority": guess_seniority(title),
            "tags": [role],
            "posted_date": datetime.utcnow(),
            "raw": {},
        })
    return out


def fetch(role: str, region: str = "", max_pages: int = 10) -> list[dict]:
    client = get_client()
    if not client:
        return []

    urls = _search_urls(client, role, region)[:max_pages]
    results = parallel_map(lambda url: _scrape_one(client, role, region, url), urls)
    return [job for batch in results if batch for job in batch]
