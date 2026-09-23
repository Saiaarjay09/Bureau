"""Firecrawl-based career-page discovery: given a company name + domain,
find their careers page and extract current job listings from it.

Complements the keyless job-board APIs (Remotive/Arbeitnow/RemoteOK), which
only cover companies that specifically post to those boards — most
companies only list openings on their own site. Triggered manually (see
routers/ingest.py) rather than on the background schedule, since each call
spends Firecrawl credits."""

import logging
from datetime import datetime

from ...enrichment import guess_seniority
from ..concurrency import parallel_map
from ..firecrawl_client import get_client
from ..location import parse_location

logger = logging.getLogger("bureau.sources.firecrawl_careers")

JOB_LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "location": {"type": "string"},
                    "department": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["title"],
            },
        }
    },
    "required": ["jobs"],
}


def _link_url(link) -> str | None:
    if isinstance(link, dict):
        return link.get("url")
    return getattr(link, "url", None)


def _find_careers_url(client, domain: str) -> str | None:
    try:
        result = client.map(f"https://{domain}", search="careers", limit=10)
    except Exception:
        logger.exception("Firecrawl map failed for %s", domain)
        return None
    links = getattr(result, "links", None) or []
    for link in links:
        url = _link_url(link)
        if url and any(kw in url.lower() for kw in ("career", "job")):
            return url
    return None


def fetch_for_company(company_name: str, domain: str) -> list[dict]:
    client = get_client()
    if not client:
        return []
    careers_url = _find_careers_url(client, domain)
    if not careers_url:
        return []

    try:
        doc = client.scrape(
            careers_url,
            formats=[{
                "type": "json",
                "prompt": (
                    "Extract every current open job listing on this careers page: "
                    "title, location (city/country if shown), department, and the "
                    "direct URL to the listing if present."
                ),
                "schema": JOB_LISTING_SCHEMA,
            }],
            only_main_content=True,
        )
    except Exception:
        logger.exception("Firecrawl scrape failed for %s", careers_url)
        return []

    data = getattr(doc, "json", None) or {}
    jobs = data.get("jobs", []) if isinstance(data, dict) else []

    out = []
    for job in jobs:
        title = (job.get("title") or "").strip()
        if not title:
            continue
        continent, country, city = parse_location(job.get("location"))
        out.append({
            "lead_type": "job",
            "source": "firecrawl_careers",
            "external_id": f"{domain}:{title}:{job.get('location', '')}".lower().replace(" ", "-")[:200],
            "title": title,
            "company": company_name,
            "company_domain": domain,
            "url": job.get("url") or careers_url,
            "continent": continent,
            "country": country,
            "city": city,
            "remote_type": "remote" if not city and not country else "onsite",
            "seniority": guess_seniority(title),
            "tags": [job.get("department")] if job.get("department") else [],
            "posted_date": datetime.utcnow(),
            "raw": {"department": job.get("department")},
        })
    return out


def fetch_for_companies(companies: list[dict]) -> list[dict]:
    """companies: [{"name": ..., "domain": ...}, ...]. Each company's
    map+scrape is independent of every other's, so they run concurrently."""
    valid = [c for c in companies if c.get("domain") and c.get("name")]
    results = parallel_map(lambda c: fetch_for_company(c["name"], c["domain"]), valid)
    return [job for batch in results if batch for job in batch]
