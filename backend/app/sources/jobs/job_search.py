"""General job search over the open web, free and local.

Reaches what the three keyless job-board APIs structurally can't:
leadership titles (they skew toward individual-contributor tech roles)
and non-Western regions (Remotive/RemoteOK are remote-only, Arbeitnow is
Europe-centric, and Adzuna — the other free-tier option — has no Middle
East coverage at all).

Previously this went through Firecrawl. It now uses sources/web.py:
DuckDuckGo for search, httpx-then-browser for fetching, and the local
Ollama for extraction. No API key, no credits, no per-call cost — which
also means it no longer has to be rationed, though it's still manual
because each run takes a couple of minutes of local compute.
"""

import logging
from datetime import datetime

from ...enrichment import guess_seniority
from .. import web
from ..concurrency import parallel_map
from ..html_text import html_to_text
from ..location import parse_location

logger = logging.getLogger("bureau.sources.job_search")

JOB_LISTING_SCHEMA = {
    "jobs": [
        {
            "title": "string",
            "company": "string",
            "location": "string — city and country if shown",
            "remote_type": "string — remote, hybrid or onsite, only if stated",
            "url": "string — direct link to the listing if present",
            "description": "string — the posting's own text, if this page shows it",
        }
    ]
}

QUERY_TEMPLATES = [
    "{role} jobs in {region}",
    "{role} job openings {region} hiring now",
    "{role} vacancy {region}",
]

RESULTS_PER_QUERY = 5


def _search_urls(role: str, region: str, per_query: int = RESULTS_PER_QUERY) -> list[str]:
    queries = [t.format(role=role, region=region or "").strip() for t in QUERY_TEMPLATES]
    batches = parallel_map(lambda q: [r.url for r in web.search(q, limit=per_query)], queries)
    urls = [url for batch in batches if batch for url in batch]
    return list(dict.fromkeys(urls))  # dedupe, keep first-seen order


def _scrape_one(role: str, region: str, url: str) -> list[dict]:
    text = web.fetch_text(url)
    if not text:
        return []

    # Deliberately does NOT ask the model to filter by role or region, which
    # was measured losing real leads: a page found by searching "IT Director
    # in UAE" listed a Riyadh role, and the model dutifully returned nothing
    # because it wasn't in the UAE. The search already did the targeting, the
    # per-job location is captured below, and the app has its own region
    # filter — so a second, stricter filter here only discards good leads.
    prompt = (
        "Extract every job listing shown on this page. For each one give the "
        "job title, the hiring company, the location, whether it is remote, "
        "hybrid or onsite if stated, a direct link if present, and the "
        "posting's own description text where the page shows it. Ignore site "
        "navigation, cookie banners, adverts and 'related searches' links."
    )
    data = web.extract(text, prompt, JOB_LISTING_SCHEMA)
    jobs = (data or {}).get("jobs") or []
    if not isinstance(jobs, list):
        return []

    out = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        title = str(job.get("title") or "").strip()
        company = str(job.get("company") or "").strip()
        if not title or not company:
            continue
        # Fall back to the searched region when a listing doesn't state its
        # own location — the search itself was already scoped to it.
        continent, country, city = parse_location(str(job.get("location") or "") or region)
        remote_type = str(job.get("remote_type") or "").strip().lower() or None
        if remote_type not in ("remote", "hybrid", "onsite"):
            remote_type = None
        out.append({
            "lead_type": "job",
            "source": "web_jobs",
            "external_id": f"{url}:{title}:{company}".lower().replace(" ", "-")[:200],
            "title": title,
            "company": company,
            "company_domain": None,
            "url": str(job.get("url") or url),
            "continent": continent,
            "country": country,
            "city": city,
            "remote_type": remote_type,
            "seniority": guess_seniority(title),
            "description": html_to_text(str(job.get("description") or "")),
            "tags": [role],
            "posted_date": datetime.utcnow(),
            "raw": {},
        })
    return out


def fetch(role: str, region: str = "", max_pages: int = 10) -> list[dict]:
    urls = _search_urls(role, region)[:max_pages]
    results = parallel_map(lambda url: _scrape_one(role, region, url), urls)
    return [job for batch in results if batch for job in batch]


def fetch_scoped(query: str, region: str = "", domains: list[str] | None = None,
                 max_pages: int = 3) -> list[dict]:
    """One raw query, optionally confined to specific domains — what the
    discovered-sites sweep uses. Doesn't fan out across query templates:
    the domain is already the narrowing."""
    results = web.search(query, limit=max_pages, include_domains=domains)
    urls = [r.url for r in results][:max_pages]
    batches = parallel_map(lambda url: _scrape_one(query, region, url), urls)
    return [job for batch in batches if batch for job in batch]
