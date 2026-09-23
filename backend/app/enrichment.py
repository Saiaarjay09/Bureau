"""Lightweight enrichment that doesn't need an external API: seniority
guessed from title text, and a "growth signal" computed by counting how
many roles a company has open right now within the same ingest window."""

import re
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .db import Lead

_SENIOR_RE = re.compile(r"\b(senior|sr\.?|staff|principal|lead|head of|director|vp|chief)\b", re.I)
_JUNIOR_RE = re.compile(r"\b(junior|jr\.?|intern|entry.level|graduate|apprentice)\b", re.I)


def guess_seniority(title: str) -> str:
    if _SENIOR_RE.search(title):
        return "senior"
    if _JUNIOR_RE.search(title):
        return "junior"
    return "mid"


def apply_growth_signals(db: Session, window_days: int = 30) -> int:
    """For job leads with no signal yet, note how many other open roles the
    same company has right now — a rough proxy for active growth/hiring."""
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    rows = (
        db.query(Lead.company)
        .filter(Lead.lead_type == "job", Lead.posted_date >= cutoff)
        .all()
    )
    counts = Counter(r[0] for r in rows)

    updated = 0
    leads = db.query(Lead).filter(Lead.lead_type == "job", Lead.posted_date >= cutoff).all()
    for lead in leads:
        n = counts.get(lead.company, 1)
        if n >= 2:
            new_signal = f"Hiring {n} roles in the last {window_days} days"
            if lead.signal != new_signal:
                lead.signal = new_signal
                updated += 1
    db.commit()
    return updated
