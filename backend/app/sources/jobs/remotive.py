"""Remotive public API — no key required. https://remotive.com/api/remote-jobs"""

import logging
from datetime import datetime

import httpx

from ...enrichment import guess_seniority
from ..location import parse_location

logger = logging.getLogger("bureau.sources.remotive")
API_URL = "https://remotive.com/api/remote-jobs"


def fetch() -> list[dict]:
    try:
        resp = httpx.get(API_URL, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Remotive fetch failed")
        return []

    jobs = resp.json().get("jobs", [])
    out = []
    for job in jobs:
        continent, country, city = parse_location(job.get("candidate_required_location"))
        try:
            posted = datetime.fromisoformat(job["publication_date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            posted = None
        out.append({
            "lead_type": "job",
            "source": "remotive",
            "external_id": str(job["id"]),
            "title": job.get("title", "").strip(),
            "company": job.get("company_name", "").strip(),
            "company_domain": None,
            "url": job.get("url"),
            "continent": continent,
            "country": country,
            "city": city,
            "remote_type": "remote",
            "seniority": guess_seniority(job.get("title", "")),
            "tags": (job.get("tags") or [])[:10],
            "posted_date": posted,
            "raw": {"category": job.get("category"), "job_type": job.get("job_type")},
        })
    return out
