"""Business-opportunity discovery: companies showing a buying signal.

Searches public sources for funding rounds, hiring surges, market
expansion and leadership changes, then pulls out the company behind each
with COMPANY-level contact info only — never a scraped personal email or
phone of a named individual.

Crunchbase and LinkedIn company pages are in scope per explicit sign-off,
despite both prohibiting scraping in their Terms of Service — see the
README. Only public, unauthenticated pages are ever touched. Note that
both now refuse a plain HTTP fetch and are only reachable via the browser
tier in sources/web.py, and LinkedIn in particular will often refuse
outright; those simply come back empty rather than failing the run.

Runs free and locally (see sources/web.py) — no Firecrawl, no credits.
"""

import logging
from datetime import datetime

from .. import web
from ..concurrency import parallel_map
from ..location import parse_location

logger = logging.getLogger("bureau.sources.company_signals")

COMPANY_SCHEMA = {
    "company_name": "string",
    "domain": "string — the company's own website domain",
    "industry": "string",
    "hq_city": "string",
    "hq_country": "string",
    "company_size": "string — approximate employee count if stated",
    "funding_stage": "string — if stated",
    "signal": "string — the specific recent event making this a live sales lead",
    "contact_path": "string — a general company contact: an inquiry email pattern or "
                    "contact-page URL. NEVER a named individual's personal email or phone",
    "found": "boolean — false if this page isn't about a specific company",
}

QUERY_TEMPLATES = [
    "{industry} company {region} raised funding recently",
    "{industry} startup {region} hiring aggressively expansion",
    "{industry} company {region} new office market expansion announcement",
    "{industry} company {region} new CEO OR new VP appointed",
]

RESULTS_PER_QUERY = 5


def _search_urls(industry: str, region: str, per_query: int = RESULTS_PER_QUERY) -> list[str]:
    queries = [t.format(industry=industry, region=region or "").strip() for t in QUERY_TEMPLATES]
    batches = parallel_map(lambda q: [r.url for r in web.search(q, limit=per_query)], queries)
    urls = [url for batch in batches if batch for url in batch]
    return list(dict.fromkeys(urls))


def _scrape_one(industry: str, url: str) -> dict | None:
    text = web.fetch_text(url)
    if not text:
        return None

    prompt = (
        "This page should be about a company. Extract its name, domain, industry, "
        "HQ city and country, approximate employee count, funding stage if known, "
        "and the specific recent signal that makes it a live sales or business "
        "opportunity right now. For the contact, give only a general company "
        "contact — an inquiry email pattern or a contact-page URL — and never a "
        "named individual's personal email or phone number. If the page covers "
        "several companies, pick the single most prominent one. Set found to "
        "false if it isn't about a company at all."
    )
    data = web.extract(text, prompt, COMPANY_SCHEMA)
    if not data or not data.get("found") or not data.get("company_name"):
        return None

    continent, country, city = parse_location(
        ", ".join(str(p) for p in [data.get("hq_city"), data.get("hq_country")] if p)
    )
    name = str(data["company_name"]).strip()
    domain = str(data.get("domain") or "").strip()
    return {
        "lead_type": "business",
        "source": "web_business",
        "external_id": (domain or name).lower().replace(" ", "-")[:200],
        "title": f"{industry} opportunity: {name}",
        "company": name,
        "company_domain": domain or None,
        "url": url,
        "continent": continent,
        "country": country,
        "city": city,
        "industry": str(data.get("industry") or industry),
        "contact_path": str(data.get("contact_path") or "") or None,
        "company_size": str(data.get("company_size") or "") or None,
        "funding_stage": str(data.get("funding_stage") or "") or None,
        "signal": str(data.get("signal") or "") or None,
        "description": text[:4000],
        "tags": [industry],
        "posted_date": datetime.utcnow(),
        "raw": {},
    }


def fetch(industry: str, region: str = "", max_companies: int = 15) -> list[dict]:
    urls = _search_urls(industry, region)[:max_companies]
    leads = parallel_map(lambda url: _scrape_one(industry, url), urls)
    return [lead for lead in leads if lead]
