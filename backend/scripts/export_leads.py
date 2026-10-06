#!/usr/bin/env python3
"""Export leads from the local database into a snapshot the static site ships.

WHY THIS EXISTS

The GitHub Pages build can refetch the three keyless job APIs itself —
they're plain HTTP and need nothing local. What it cannot regenerate is
anything that came from the web-scraping sources, because those need the
local Ollama to turn a page into structured leads. That's precisely where
the regional coverage lives: the UAE, Gulf and APAC leads the keyless
boards don't carry at all.

So those get exported here, committed, and merged by the site build. The
Mac has to be awake to run this, but only for the minute it takes —
not continuously, which was the whole point of moving to Pages.

WHAT IS DELIBERATELY NOT EXPORTED

Anything personal. `fit_score`/`fit_reason` and the `council_*` verdicts
are judgements about one specific CV, and the starred flags are a private
shortlist; publishing those to a public site would leak what someone is
applying for and how well they match. Only the posting itself — which was
public to begin with — goes out.

    python3 backend/scripts/export_leads.py
    python3 backend/scripts/export_leads.py --limit 400 --days 45
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Lead, SessionLocal  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "site" / "data" / "snapshot.json"

# Sources the CI build can refetch on its own; exporting them would just
# duplicate work and bloat the committed file.
REFETCHABLE = {"remotive", "arbeitnow", "remoteok"}
EXCLUDED = REFETCHABLE | {"mock"}

MAX_DESCRIPTION_CHARS = 1500


def lead_to_public(lead: Lead) -> dict:
    """Only the posting. See the note above about what's withheld."""
    description = (lead.description or "").strip()
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[:MAX_DESCRIPTION_CHARS].rstrip() + "…"
    return {
        "lead_type": lead.lead_type,
        "source": lead.source,
        "title": lead.title,
        "company": lead.company,
        "company_domain": lead.company_domain,
        "url": lead.url,
        "continent": lead.continent,
        "country": lead.country,
        "city": lead.city,
        "remote_type": lead.remote_type,
        "seniority": lead.seniority,
        "industry": lead.industry,
        "contact_path": lead.contact_path,
        "company_size": lead.company_size,
        "funding_stage": lead.funding_stage,
        "signal": lead.signal,
        "description": description or None,
        "posted_date": lead.posted_date.isoformat() if lead.posted_date else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=800, help="Max leads per lead type")
    parser.add_argument("--days", type=int, default=60, help="Only leads seen this recently")
    args = parser.parse_args()

    # Naive UTC: the DB stores timestamps without tzinfo, so an aware value
    # here wouldn't compare against them.
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=args.days)
    db = SessionLocal()
    try:
        # Per-type limits, not one global one. A single limit let the far more
        # numerous job leads fill the whole quota and exported zero business
        # leads, silently emptying that whole tab on the published site.
        leads = []
        for lead_type in ("job", "business"):
            rows = (
                db.query(Lead)
                .filter(
                    Lead.lead_type == lead_type,
                    Lead.source.notin_(EXCLUDED),
                    Lead.updated_at >= cutoff,
                )
                .order_by(Lead.posted_date.desc().nulls_last())
                .limit(args.limit)
                .all()
            )
            leads.extend(lead_to_public(lead) for lead in rows)
    finally:
        db.close()

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "note": "Locally-scraped leads the CI build can't regenerate. No personal "
                "match scores or starred flags are included.",
        "leads": leads,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, separators=(",", ":")) + "\n")

    by_source: dict[str, int] = {}
    for lead in leads:
        by_source[lead["source"]] = by_source.get(lead["source"], 0) + 1
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} — {len(leads)} leads, {size_kb:.0f} KB")
    for source, count in sorted(by_source.items()):
        print(f"  {source:16} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
