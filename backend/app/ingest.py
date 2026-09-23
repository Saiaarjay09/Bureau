"""Shared upsert helper: every source module normalizes to this dict shape
and hands it to upsert_leads(), which dedupes on (source, external_id)."""

import json
import logging
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from .db import Lead

logger = logging.getLogger("bureau.ingest")

REQUIRED_FIELDS = {"lead_type", "source", "external_id", "title", "company"}


def upsert_leads(db: Session, leads: Iterable[dict[str, Any]]) -> tuple[int, int]:
    """Insert new leads / update existing ones. Returns (created, updated).

    Dedupes on (source, external_id) both against already-committed rows
    AND within the batch itself — a source can legitimately hand back the
    same job twice (e.g. matched by two different search queries), and
    without the in-batch check the second one would still look "new" to
    a plain SELECT (it hasn't been flushed yet) and crash the whole batch
    on SQLite's UNIQUE constraint at commit time instead of updating."""
    created = updated = 0
    pending: dict[tuple[str, str], Lead] = {}
    for raw in leads:
        missing = REQUIRED_FIELDS - raw.keys()
        if missing:
            logger.warning("skipping lead missing fields %s: %r", missing, raw.get("external_id"))
            continue

        tags = raw.pop("tags", None) or []
        raw = dict(raw)
        raw["tags_json"] = json.dumps(tags)
        raw["raw_json"] = json.dumps(raw.pop("raw", None) or {})

        key = (raw["source"], raw["external_id"])
        existing = pending.get(key) or (
            db.query(Lead)
            .filter(Lead.source == raw["source"], Lead.external_id == raw["external_id"])
            .one_or_none()
        )
        if existing:
            for field, value in raw.items():
                if field == "starred":
                    continue
                setattr(existing, field, value)
            existing.updated_at = datetime.utcnow()
            if key not in pending:
                updated += 1
        else:
            lead = Lead(**raw)
            db.add(lead)
            pending[key] = lead
            created += 1
    db.commit()
    return created, updated
