"""Background loop that periodically refreshes the keyless job-board
sources. Firecrawl-based sources are deliberately excluded — they cost
credits, so they only run when triggered manually via /api/ingest/*."""

import asyncio
import logging

from .config import INGEST_INTERVAL_SECONDS
from .db import SessionLocal
from .enrichment import apply_growth_signals
from .ingest import upsert_leads
from .sources.registry import JOB_FETCHERS

logger = logging.getLogger("scout.scheduler")

LAST_RUN: dict[str, str] = {}


def run_job_sources_once() -> dict[str, tuple[int, int]]:
    results = {}
    db = SessionLocal()
    try:
        for name, fetcher in JOB_FETCHERS.items():
            try:
                leads = fetcher()
            except Exception:
                logger.exception("job source %s raised", name)
                continue
            created, updated = upsert_leads(db, leads)
            results[name] = (created, updated)
            logger.info("%s: %d created, %d updated", name, created, updated)
        apply_growth_signals(db)
    finally:
        db.close()
    return results


async def background_loop():
    from datetime import datetime, timezone

    while True:
        try:
            run_job_sources_once()
            LAST_RUN["jobs"] = datetime.now(timezone.utc).isoformat()
        except Exception:
            logger.exception("background ingest loop failed")
        await asyncio.sleep(INGEST_INTERVAL_SECONDS)
