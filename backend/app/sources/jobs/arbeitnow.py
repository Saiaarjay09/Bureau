"""Arbeitnow public job board API — no key required.
https://www.arbeitnow.com/api/job-board-api"""

import logging
from datetime import datetime, timezone

import httpx

from ...enrichment import guess_seniority
from ..location import parse_location

logger = logging.getLogger("scout.sources.arbeitnow")
API_URL = "https://www.arbeitnow.com/api/job-board-api"


def fetch() -> list[dict]:
    try:
        resp = httpx.get(API_URL, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Arbeitnow fetch failed")
        return []

    jobs = resp.json().get("data", [])
    out = []
    for job in jobs:
        continent, country, city = parse_location(job.get("location"))
        posted = None
        if job.get("created_at"):
            try:
                posted = datetime.fromtimestamp(int(job["created_at"]), tz=timezone.utc)
            except (ValueError, OSError):
                posted = None
        out.append({
            "lead_type": "job",
            "source": "arbeitnow",
            "external_id": job.get("slug") or job.get("url", ""),
            "title": job.get("title", "").strip(),
            "company": job.get("company_name", "").strip(),
            "company_domain": None,
            "url": job.get("url"),
            "continent": continent,
            "country": country,
            "city": city,
            "remote_type": "remote" if job.get("remote") else "onsite",
            "seniority": guess_seniority(job.get("title", "")),
            "tags": (job.get("tags") or [])[:10],
            "posted_date": posted,
            "raw": {"job_types": job.get("job_types")},
        })
    return out
