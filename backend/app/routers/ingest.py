from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_session
from ..db import SessionLocal
from ..enrichment import apply_growth_signals
from ..ingest import upsert_leads
from ..scheduler import LAST_RUN, run_job_sources_once
from ..sources.business import firecrawl_business
from ..sources.firecrawl_client import is_configured
from ..sources.jobs import firecrawl_careers

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


@router.get("/status")
def status():
    return {"firecrawl_configured": is_configured(), "last_run": LAST_RUN}


@router.post("/jobs")
def ingest_jobs():
    """Refresh the keyless job-board sources (Remotive/Arbeitnow/RemoteOK) right now."""
    results = run_job_sources_once()
    return {"results": results}


@router.post("/careers")
def ingest_careers(body: CareersRequest):
    """Firecrawl career-page discovery for specific companies. Spends Firecrawl credits."""
    if not is_configured():
        raise HTTPException(status_code=400, detail="FIRECRAWL_API_KEY is not set on the server")
    leads = firecrawl_careers.fetch_for_companies([c.model_dump() for c in body.companies])
    db = SessionLocal()
    try:
        created, updated = upsert_leads(db, leads)
        apply_growth_signals(db)
    finally:
        db.close()
    return {"created": created, "updated": updated}


@router.post("/business")
def ingest_business(body: BusinessRequest):
    """Firecrawl-based business-opportunity discovery for one industry/region. Spends Firecrawl credits."""
    if not is_configured():
        raise HTTPException(status_code=400, detail="FIRECRAWL_API_KEY is not set on the server")
    leads = firecrawl_business.fetch(body.industry, body.region or "", body.max_companies)
    db = SessionLocal()
    try:
        created, updated = upsert_leads(db, leads)
    finally:
        db.close()
    return {"created": created, "updated": updated}
