import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_session
from ..db import Lead, SessionLocal, utcnow
from ..sabha import clear_cv, cv_status, cv_text, run_council, sabha_health, set_cv, summarise_council
from ..screener import STATE, outstanding_count, rescore_all

logger = logging.getLogger("bureau.match")

router = APIRouter(prefix="/api/match", tags=["match"], dependencies=[Depends(require_session)])


class CVRequest(BaseModel):
    text: str


@router.get("/status")
def status():
    return {
        "cv": cv_status(),
        "sabha": sabha_health(),
        "screening": {**STATE, "remaining": outstanding_count()},
    }


@router.put("/cv")
def put_cv(body: CVRequest):
    text = body.text.strip()
    if len(text) < 200:
        raise HTTPException(status_code=400, detail="That CV is too short to match against — paste the full text.")
    set_cv(text)
    # Scores computed against a previous CV are actively misleading once it
    # changes, so they're cleared rather than left to age.
    cleared = rescore_all()
    return {**cv_status(), "rescoring": cleared}


@router.delete("/cv")
def delete_cv():
    clear_cv()
    cleared = rescore_all()
    return {"ok": True, "cleared_scores": cleared}


def _council_task(lead_id: int, title: str, description: str | None, cv: str) -> None:
    """Runs in a background thread — a council run is minutes long, far past
    any sensible HTTP timeout, so the request returns immediately and the
    frontend polls the lead for the verdict."""
    db = SessionLocal()
    try:
        result = run_council(title, description, cv)
        summary = summarise_council(result)
        lead = db.get(Lead, lead_id)
        if lead:
            lead.council_status = "done"
            lead.council_score = summary["score"]
            lead.council_match_pct = summary["match_pct"]
            lead.council_json = json.dumps(result)
            lead.council_run_at = utcnow()
            db.commit()
    except Exception as exc:
        logger.exception("council run failed for lead %s", lead_id)
        lead = db.get(Lead, lead_id)
        if lead:
            lead.council_status = "failed"
            lead.council_json = json.dumps({"error": str(exc)})
            lead.council_run_at = utcnow()
            db.commit()
    finally:
        db.close()


@router.post("/council/{lead_id}")
def start_council(lead_id: int, background: BackgroundTasks):
    cv = cv_text()
    if not cv:
        raise HTTPException(status_code=400, detail="No CV set yet — add one before running the council.")

    health = sabha_health()
    if not health.get("available"):
        raise HTTPException(
            status_code=503,
            detail="Sabha isn't reachable on this machine. Start the council service (port 8700) and try again.",
        )

    db = SessionLocal()
    try:
        lead = db.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        if lead.council_status == "running":
            raise HTTPException(status_code=409, detail="A council run is already in flight for this lead.")
        if not (lead.description or "").strip():
            raise HTTPException(
                status_code=400,
                detail="No description was captured for this lead, so there's nothing for the council to assess.",
            )
        title, description = lead.title, lead.description
        lead.council_status = "running"
        lead.council_run_at = utcnow()
        db.commit()
    finally:
        db.close()

    background.add_task(_council_task, lead_id, title, description, cv)
    return {"status": "running", "lead_id": lead_id}
