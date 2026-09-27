"""Career-page discovery for specific companies.

Complements the keyless job-board APIs, which only cover companies that
post to those boards — most companies only list openings on their own
site.

Firecrawl's `map` used to enumerate a domain's URLs to find the careers
page. Without it, this tries the handful of paths companies actually use
(/careers, /jobs, …) and falls back to a site-scoped search. That's less
thorough than a real crawl, but it costs nothing and those conventional
paths cover the large majority of company sites.
"""

import logging
from datetime import datetime

from ...enrichment import guess_seniority
from .. import web
from ..concurrency import parallel_map
from ..html_text import html_to_text
from ..location import parse_location

logger = logging.getLogger("bureau.sources.career_pages")

JOB_LISTING_SCHEMA = {
    "jobs": [
        {
            "title": "string",
            "location": "string — city and country if shown",
            "department": "string",
            "url": "string — direct link to the listing if present",
            "description": "string — the posting's own text, if shown",
        }
    ]
}

CANDIDATE_PATHS = ["/careers", "/jobs", "/careers/jobs", "/about/careers", "/company/careers", "/join-us"]


def _find_careers_url(domain: str) -> str | None:
    """Conventional paths first — one cheap HTTP HEAD-ish fetch each — then
    a site-scoped search as a fallback."""
    for path in CANDIDATE_PATHS:
        url = f"https://{domain.rstrip('/')}{path}"
        # No browser here: this is a probe, and starting Chromium six times
        # to discover a URL would cost more than the page is worth.
        if web.fetch_text(url, allow_browser=False):
            return url

    results = web.search("careers jobs openings", limit=3, include_domains=[domain])
    for result in results:
        if any(kw in result.url.lower() for kw in ("career", "job", "vacan")):
            return result.url
    return None


def fetch_for_company(company_name: str, domain: str) -> list[dict]:
    careers_url = _find_careers_url(domain)
    if not careers_url:
        return []

    text = web.fetch_text(careers_url)
    if not text:
        return []

    data = web.extract(
        text,
        "Extract every current open job listing on this careers page: title, "
        "location, department, and the direct URL to the listing if present. "
        "Ignore navigation and marketing copy.",
        JOB_LISTING_SCHEMA,
    )
    jobs = (data or {}).get("jobs") or []
    if not isinstance(jobs, list):
        return []

    out = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        title = str(job.get("title") or "").strip()
        if not title:
            continue
        continent, country, city = parse_location(str(job.get("location") or ""))
        department = str(job.get("department") or "").strip()
        out.append({
            "lead_type": "job",
            "source": "web_careers",
            "external_id": f"{domain}:{title}:{job.get('location', '')}".lower().replace(" ", "-")[:200],
            "title": title,
            "company": company_name,
            "company_domain": domain,
            "url": str(job.get("url") or careers_url),
            "continent": continent,
            "country": country,
            "city": city,
            "remote_type": "remote" if not city and not country else "onsite",
            "seniority": guess_seniority(title),
            "description": html_to_text(str(job.get("description") or "")),
            "tags": [department] if department else [],
            "posted_date": datetime.utcnow(),
            "raw": {"department": department},
        })
    return out


def fetch_for_companies(companies: list[dict]) -> list[dict]:
    """companies: [{"name": ..., "domain": ...}, ...]. Each company's probe
    and scrape is independent, so they run concurrently."""
    valid = [c for c in companies if c.get("domain") and c.get("name")]
    results = parallel_map(lambda c: fetch_for_company(c["name"], c["domain"]), valid)
    return [job for batch in results if batch for job in batch]
