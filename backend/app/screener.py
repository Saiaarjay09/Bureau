"""Background screening of unscored leads against the stored CV.

Runs continuously but politely: one lead at a time, and it stands down
entirely whenever Sabha has a council run in flight. That deference is the
point — a council run is something a person is sitting and waiting five
minutes for, and the screen is bulk work nobody is watching. Both want the
same GPU, so the interactive one wins.

State is the `fit_score` column itself: anything NULL is outstanding. That
makes the whole thing resumable across restarts with no separate queue or
progress file to keep in sync.
"""

import asyncio
import logging

import httpx

from .config import SABHA_URL
from .db import Lead, SessionLocal, utcnow
from .sabha import cv_text, quick_screen

logger = logging.getLogger("bureau.screener")

IDLE_SLEEP_SECONDS = 60
BUSY_SLEEP_SECONDS = 30

STATE: dict[str, object] = {"running": False, "screened": 0, "remaining": None, "paused_for_council": False}


def _council_busy() -> bool:
    """True when Sabha is mid-run, so bulk screening should get out of the
    way. A failure to reach Sabha is treated as 'not busy': if the service
    is down there is no council run to protect."""
    try:
        resp = httpx.get(f"{SABHA_URL}/api/health", timeout=3)
        resp.raise_for_status()
        return int(resp.json().get("active_runs") or 0) > 0
    except (httpx.HTTPError, ValueError):
        return False


def outstanding_count() -> int:
    db = SessionLocal()
    try:
        return db.query(Lead).filter(Lead.fit_score.is_(None)).count()
    except Exception:
        return 0
    finally:
        db.close()


def screen_one(cv: str) -> bool:
    """Screens a single unscored lead. Returns False when there's nothing
    left to do (or the model failed, which also ends this pass so a broken
    Ollama doesn't spin through every remaining lead logging failures)."""
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.fit_score.is_(None)).order_by(Lead.id.desc()).first()
        if not lead:
            return False

        result = quick_screen(lead.title, lead.company, lead.description, cv)
        if result is None:
            return False

        score, reason = result
        lead.fit_score = score
        lead.fit_reason = reason
        lead.fit_scored_at = utcnow()
        db.commit()
        STATE["screened"] = int(STATE.get("screened") or 0) + 1
        return True
    finally:
        db.close()


async def background_loop():
    """Started from main.py's lifespan alongside the ingest loop."""
    while True:
        try:
            cv = cv_text()
            if not cv:
                STATE["running"] = False
                await asyncio.sleep(IDLE_SLEEP_SECONDS)
                continue

            if await asyncio.to_thread(_council_busy):
                STATE["paused_for_council"] = True
                await asyncio.sleep(BUSY_SLEEP_SECONDS)
                continue
            STATE["paused_for_council"] = False

            did_work = await asyncio.to_thread(screen_one, cv)
            STATE["running"] = did_work
            STATE["remaining"] = await asyncio.to_thread(outstanding_count)
            if not did_work:
                await asyncio.sleep(IDLE_SLEEP_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("screener loop iteration failed")
            await asyncio.sleep(IDLE_SLEEP_SECONDS)


def rescore_all() -> int:
    """Clears every score so the loop re-does them — used when the CV changes,
    since a score against an old CV is worse than none.

    This clears council verdicts as well, not just screen scores. A council
    verdict is the more authoritative number and the one a person will act
    on, so leaving a stale one on the card while its screen score vanished
    would be exactly backwards. They cost five minutes each to regenerate,
    but only for leads someone chooses to re-run."""
    db = SessionLocal()
    try:
        n = db.query(Lead).filter(Lead.fit_score.isnot(None)).update(
            {Lead.fit_score: None, Lead.fit_reason: None, Lead.fit_scored_at: None},
            synchronize_session=False,
        )
        # Deliberately not filtered on council_status == "running": a run in
        # flight was started against the old CV too, and its result would be
        # written back afterwards. Clearing here means the stale verdict is
        # at least not presented as current.
        db.query(Lead).filter(Lead.council_score.isnot(None)).update(
            {
                Lead.council_status: None,
                Lead.council_score: None,
                Lead.council_match_pct: None,
                Lead.council_json: None,
                Lead.council_run_at: None,
            },
            synchronize_session=False,
        )
        db.commit()
        STATE["screened"] = 0
        return n
    finally:
        db.close()
