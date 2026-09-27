from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_session
from ..db import SessionLocal
from ..enrichment import apply_growth_signals
from ..ingest import upsert_leads
from ..scheduler import LAST_RUN, run_job_sources_once
from ..sources.business import company_signals
from ..sources.web import is_available
from ..sources.jobs import career_pages, job_search

OLLAMA_DOWN = (
    "Ollama isn't reachable on this machine, and it's what extracts structured "
    "leads from fetched pages. Start it and try again."
)

router = APIRouter(prefix="/api/ingest", tags=["ingest"], dependencies=[Depends(require_session)])


class CompanyRef(BaseModel):
    name: str
    domain: str


class CareersRequest(BaseModel):
    companies: list[CompanyRef]


class BusinessRequest(BaseModel):
    industry: str
    region: Optional[str] = ""
    max_companies: int = 15


class JobSearchRequest(BaseModel):
    role: str
    region: Optional[str] = ""
    max_pages: int = 10


@router.get("/status")
def status():
    return {"web_available": is_available(), "last_run": LAST_RUN}


@router.post("/jobs")
def ingest_jobs():
    """Refresh the keyless job-board sources (Remotive/Arbeitnow/RemoteOK) right now."""
    results = run_job_sources_once()
    return {"results": results}


@router.post("/careers")
def ingest_careers(body: CareersRequest):
    """Career-page discovery for specific companies, free and local."""
    if not is_available():
        raise HTTPException(status_code=503, detail=OLLAMA_DOWN)
    leads = career_pages.fetch_for_companies([c.model_dump() for c in body.companies])
    db = SessionLocal()
    try:
        created, updated = upsert_leads(db, leads)
        apply_growth_signals(db)
    finally:
        db.close()
    return {"created": created, "updated": updated}


@router.post("/business")
def ingest_business(body: BusinessRequest):
    """Business-opportunity discovery for one industry/region, free and local."""
    if not is_available():
        raise HTTPException(status_code=503, detail=OLLAMA_DOWN)
    leads = company_signals.fetch(body.industry, body.region or "", body.max_companies)
    db = SessionLocal()
    try:
        created, updated = upsert_leads(db, leads)
    finally:
        db.close()
    return {"created": created, "updated": updated}


@router.post("/job_search")
def ingest_job_search(body: JobSearchRequest):
    """Job search for any role/region combo the keyless boards don't cover
    (leadership titles, non-Western regions). Free — searches the web and
    extracts with the local model — but takes a couple of minutes."""
    if not is_available():
        raise HTTPException(status_code=503, detail=OLLAMA_DOWN)
    leads = job_search.fetch(body.role, body.region or "", body.max_pages)
    db = SessionLocal()
    try:
        created, updated = upsert_leads(db, leads)
        apply_growth_signals(db)
    finally:
        db.close()
    return {"created": created, "updated": updated}
