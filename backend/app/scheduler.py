"""Background ingest loops.

Two cadences, split by what a run costs:

- The three keyless job-board APIs are free, so they refresh every few
  hours (INGEST_INTERVAL_SECONDS).
- The discovered-sites sweep goes through Firecrawl and costs credits per
  call, so it runs once a day and only over a rotating slice of the site
  list. Firecrawl's on-demand endpoints (/api/ingest/*) stay manual — a
  person clicking a button is a different thing from a loop spending
  credits unattended.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from .config import INGEST_INTERVAL_SECONDS
from .db import SessionLocal
from .enrichment import apply_growth_signals
from .ingest import upsert_leads
from .sources import discovered
from .sources.firecrawl_client import is_configured
from .sources.registry import JOB_FETCHERS

logger = logging.getLogger("bureau.scheduler")

LAST_RUN: dict[str, str] = {}
DISCOVERED_INTERVAL = timedelta(days=1)


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


def run_discovered_sites_once() -> tuple[int, int]:
    """Today's slice of the sites the GitHub Action found. Returns (created,
    updated); (0, 0) when Firecrawl isn't configured or the list is empty."""
    if not is_configured():
        return (0, 0)
    leads = discovered.fetch()
    if not leads:
        return (0, 0)
    db = SessionLocal()
    try:
        created, updated = upsert_leads(db, leads)
        apply_growth_signals(db)
        logger.info("discovered sites: %d created, %d updated", created, updated)
        return created, updated
    finally:
        db.close()


def _due(key: str, interval: timedelta) -> bool:
    last = LAST_RUN.get(key)
    if not last:
        return True
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(last) >= interval
    except ValueError:
        return True


async def background_loop():
    while True:
        try:
            run_job_sources_once()
            LAST_RUN["jobs"] = datetime.now(timezone.utc).isoformat()

            if _due("discovered", DISCOVERED_INTERVAL):
                await asyncio.to_thread(run_discovered_sites_once)
                LAST_RUN["discovered"] = datetime.now(timezone.utc).isoformat()
        except Exception:
            logger.exception("background ingest loop failed")
        await asyncio.sleep(INGEST_INTERVAL_SECONDS)
