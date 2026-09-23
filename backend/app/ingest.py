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
    """Insert new leads / update existing ones. Returns (created, updated)."""
    created = updated = 0
    for raw in leads:
        missing = REQUIRED_FIELDS - raw.keys()
        if missing:
            logger.warning("skipping lead missing fields %s: %r", missing, raw.get("external_id"))
            continue

        tags = raw.pop("tags", None) or []
        raw = dict(raw)
        raw["tags_json"] = json.dumps(tags)
        raw["raw_json"] = json.dumps(raw.pop("raw", None) or {})

        existing = (
            db.query(Lead)
            .filter(Lead.source == raw["source"], Lead.external_id == raw["external_id"])
            .one_or_none()
        )
        if existing:
            for key, value in raw.items():
                if key == "starred":
                    continue
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            updated += 1
        else:
            db.add(Lead(**raw))
            created += 1
    db.commit()
    return created, updated
