"""Fetch a single job posting's text on demand.

Two thirds of job leads arrive without a description: board entries that
aged out before descriptions were stored, and listing-page scrapes that
only showed titles. All of them have a URL.

This runs at the one moment the text is worth going to get: just before a
council run, which is about to spend five minutes of GPU either way.
Seconds spent here give those five minutes something real to assess, and
the result is written back so the screen and later runs benefit.

Extraction rather than raw page text, because raw text was tried and
rejected on evidence: a job board fetched whole came back as 20KB of
"Dismiss / Close menu / Popular / Locations" navigation with the posting
buried inside. Handing that to Sabha would be worse than a title-only
run, since its first step decomposes the posting into requirements and
would be decomposing a nav bar. Naming the role also disambiguates
aggregator pages listing many jobs at once.
"""

import logging

from . import web
from .html_text import html_to_text

logger = logging.getLogger("bureau.sources.job_description")

MIN_USEFUL_CHARS = 200

DESCRIPTION_SCHEMA = {
    "description": "string — the full text of the job posting: what the role involves, "
                   "responsibilities and requirements. Exclude navigation, cookie "
                   "banners, footers and unrelated jobs on the same page",
    "found": "boolean — false if this page does not contain the posting",
}


def fetch_description(url: str, title: str = "") -> str | None:
    """Returns the posting's text, or None — callers fall back to a
    title-only council run rather than failing."""
    text = web.fetch_text(url)
    if not text:
        return None

    prompt = (
        "Extract the job posting on this page"
        + (f" for the role '{title}'" if title else "")
        + ". Return the description and requirements as plain text. If the page "
        "lists many jobs, return only that one role's posting. If the posting "
        "isn't on this page at all, set found to false."
    )
    data = web.extract(text, prompt, DESCRIPTION_SCHEMA)
    if not data or not data.get("found"):
        return None

    description = html_to_text(str(data.get("description") or ""))
    if not description or len(description) < MIN_USEFUL_CHARS:
        return None
    return description
