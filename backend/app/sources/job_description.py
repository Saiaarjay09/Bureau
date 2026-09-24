"""Fetch a single job posting's text on demand.

Two thirds of job leads arrive without a description: Arbeitnow entries
that aged off the board before descriptions were being stored, and
firecrawl_jobs leads scraped from listing pages that only showed titles.
All of them do have a URL.

Backfilling all ~1,250 would cost a Firecrawl credit each for pages
almost none of which will ever be opened. So this runs on demand instead,
at the one moment the text is actually worth paying for: just before a
council run, which is about to spend five minutes of GPU either way. A
few seconds to give those five minutes something real to assess is an
obvious trade.

This uses schema extraction rather than plain markdown, which was tried
first and rejected: `only_main_content` left a job-board page as 20KB of
"Dismiss / Close menu / Popular / Locations / Categories" navigation with
the posting buried inside. Handing that to Sabha would be actively worse
than a title-only run, because its first step decomposes the posting into
requirements and would be decomposing a nav bar. Naming the role in the
prompt also disambiguates aggregator pages that list many jobs at once.
"""

import logging
import time

from .firecrawl_client import get_client
from .html_text import html_to_text

logger = logging.getLogger("bureau.sources.job_description")

MIN_USEFUL_CHARS = 200
# Firecrawl allows 18 requests/minute on this plan. A council run is about
# to cost five minutes of GPU, so waiting out a transient 429 rather than
# silently falling back to a title-only assessment is trivially worth it.
RATE_LIMIT_WAIT_S = 20

DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": "The full text of the job posting itself: what the role "
                           "involves, responsibilities, and the requirements asked for. "
                           "Exclude site navigation, cookie banners, footers, and any "
                           "unrelated jobs listed on the same page.",
        },
        "found": {
            "type": "boolean",
            "description": "False if this page does not actually contain the posting.",
        },
    },
    "required": ["description", "found"],
}


def fetch_description(url: str, title: str = "") -> str | None:
    """Scrapes one posting and returns its text, or None if that didn't
    work — callers fall back to a title-only run rather than failing."""
    client = get_client()
    if not client or not url:
        return None

    prompt = (
        "Extract the job posting on this page"
        + (f" for the role '{title}'" if title else "")
        + ". Return the description and requirements as plain text. If the page "
        "is a listing of many jobs, return only that one role's posting. If the "
        "posting isn't on this page at all, set found to false."
    )

    def scrape():
        return client.scrape(
            url,
            formats=[{"type": "json", "prompt": prompt, "schema": DESCRIPTION_SCHEMA}],
            only_main_content=True,
        )

    try:
        doc = scrape()
    except Exception as exc:
        # Matched on the message rather than the SDK's internal exception
        # class, which isn't part of its documented surface.
        if "rate limit" not in str(exc).lower():
            logger.exception("could not fetch description from %s", url)
            return None
        logger.info("rate limited fetching %s — waiting %ss", url, RATE_LIMIT_WAIT_S)
        time.sleep(RATE_LIMIT_WAIT_S)
        try:
            doc = scrape()
        except Exception:
            logger.exception("could not fetch description from %s after retry", url)
            return None

    data = getattr(doc, "json", None) or {}
    if not isinstance(data, dict) or not data.get("found"):
        return None

    text = html_to_text(str(data.get("description") or ""))
    if not text or len(text) < MIN_USEFUL_CHARS:
        return None
    return text
