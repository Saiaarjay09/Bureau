"""Firecrawl-based business-opportunity discovery: searches public sources
for companies showing buying/growth signals (funding, active hiring,
expansion, leadership changes) and enriches each with public, COMPANY-level
contact info only — never a scraped personal email/phone of a named
individual.

Crunchbase and LinkedIn company pages are in scope here per explicit
sign-off from the person running this tool, despite both prohibiting
scraping in their Terms of Service — see the README's "Business leads
data sources" section for that tradeoff. Only their public, unauthenticated
pages are ever touched, never anything behind a login wall. Triggered
manually (see routers/ingest.py), not on the background schedule, since
each call spends Firecrawl credits."""

import logging
from datetime import datetime

from ..firecrawl_client import get_client
from ..location import parse_location

logger = logging.getLogger("bureau.sources.firecrawl_business")

COMPANY_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "domain": {"type": "string"},
        "industry": {"type": "string"},
        "hq_city": {"type": "string"},
        "hq_country": {"type": "string"},
        "company_size": {"type": "string"},
        "funding_stage": {"type": "string"},
        "signal": {
            "type": "string",
            "description": "The specific recent event that makes this company a live "
                           "sales/business lead right now (funding round, hiring surge, "
                           "market expansion, new exec).",
        },
        "contact_path": {
            "type": "string",
            "description": "A general company contact: an inquiry email pattern "
                           "(e.g. hello@company.com) or a contact-page URL. Never a "
                           "named individual's personal email or phone number.",
        },
    },
    "required": ["company_name"],
}

QUERY_TEMPLATES = [
    "{industry} company {region} raised funding recently",
    "{industry} startup {region} hiring aggressively expansion",
    "{industry} company {region} new office market expansion announcement",
    "{industry} company {region} new CEO OR new VP appointed",
]


def _result_url(item) -> str | None:
    if isinstance(item, dict):
        return item.get("url")
    return getattr(item, "url", None)


def _search_urls(client, industry: str, region: str, limit_per_query: int = 5) -> list[str]:
    urls: list[str] = []
    for template in QUERY_TEMPLATES:
        query = template.format(industry=industry, region=region or "").strip()
        try:
            result = client.search(query, limit=limit_per_query, sources=["web", "news"])
        except Exception:
            logger.exception("Firecrawl search failed for %r", query)
            continue
        for item in (getattr(result, "web", None) or []):
            url = _result_url(item)
            if url:
                urls.append(url)
    return list(dict.fromkeys(urls))  # dedupe, keep first-seen order


def fetch(industry: str, region: str = "", max_companies: int = 15) -> list[dict]:
    client = get_client()
    if not client:
        return []

    urls = _search_urls(client, industry, region)[:max_companies]
    out = []
    for url in urls:
        try:
            doc = client.scrape(
                url,
                formats=[{
                    "type": "json",
                    "prompt": (
                        "This page is about a company. Extract its name, domain, "
                        "industry, HQ city/country, approximate employee count, "
                        "funding stage if known, the specific recent signal that "
                        "makes it a live sales/business opportunity, and a general "
                        "company contact — never a named individual's personal "
                        "email or phone."
                    ),
                    "schema": COMPANY_SCHEMA,
                }],
                only_main_content=True,
            )
        except Exception:
            logger.exception("Firecrawl scrape failed for %s", url)
            continue

        data = getattr(doc, "json", None) or {}
        if not isinstance(data, dict) or not data.get("company_name"):
            continue

        continent, country, city = parse_location(
            ", ".join(p for p in [data.get("hq_city"), data.get("hq_country")] if p)
        )
        out.append({
            "lead_type": "business",
            "source": "firecrawl_business",
            "external_id": (data.get("domain") or data["company_name"]).lower().replace(" ", "-"),
            "title": f"{industry} opportunity: {data['company_name']}",
            "company": data["company_name"],
            "company_domain": data.get("domain"),
            "url": url,
            "continent": continent,
            "country": country,
            "city": city,
            "industry": data.get("industry") or industry,
            "contact_path": data.get("contact_path"),
            "company_size": data.get("company_size"),
            "funding_stage": data.get("funding_stage"),
            "signal": data.get("signal"),
            "tags": [industry],
            "posted_date": datetime.utcnow(),
            "raw": {},
        })
    return out
