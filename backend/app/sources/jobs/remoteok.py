"""RemoteOK public API — no key required, but requires a descriptive
User-Agent or requests get 403'd. https://remoteok.com/api"""

import logging
from datetime import datetime, timezone

import httpx

from ...enrichment import guess_seniority
from ..location import parse_location

logger = logging.getLogger("scout.sources.remoteok")
API_URL = "https://remoteok.com/api"
HEADERS = {"User-Agent": "Scout-LeadGen/1.0 (+https://github.com/; personal use)"}


def fetch() -> list[dict]:
    try:
        resp = httpx.get(API_URL, timeout=30, headers=HEADERS)
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("RemoteOK fetch failed")
        return []

    rows = resp.json()
    out = []
    for job in rows:
        if "id" not in job:  # first element is a legal-notice stub, not a job
            continue
        continent, country, city = parse_location(job.get("location"))
        posted = None
        if job.get("date"):
            try:
                posted = datetime.fromisoformat(job["date"].replace("Z", "+00:00"))
            except ValueError:
                posted = None
        out.append({
            "lead_type": "job",
            "source": "remoteok",
            "external_id": str(job["id"]),
            "title": (job.get("position") or "").strip(),
            "company": (job.get("company") or "").strip(),
            "company_domain": None,
            "url": job.get("url") or job.get("apply_url"),
            "continent": continent,
            "country": country,
            "city": city,
            "remote_type": "remote",
            "seniority": guess_seniority(job.get("position") or ""),
            "tags": (job.get("tags") or [])[:10],
            "posted_date": posted.replace(tzinfo=timezone.utc) if posted and not posted.tzinfo else posted,
            "raw": {},
        })
    return out
