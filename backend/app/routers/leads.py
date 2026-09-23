import csv
import io
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import require_session
from ..db import Lead, SessionLocal
from ..regions import CONTINENTS
from ..schemas import LeadOut, LeadsPage

router = APIRouter(prefix="/api", tags=["leads"], dependencies=[Depends(require_session)])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_filters(
    query,
    lead_type: str,
    continent: Optional[str],
    country: Optional[str],
    city: Optional[str],
    search: Optional[str],
    remote_type: Optional[str],
    starred_only: bool,
):
    query = query.filter(Lead.lead_type == lead_type)
    if continent and continent != "Global":
        query = query.filter(Lead.continent == continent)
    if country:
        query = query.filter(Lead.country == country)
    if city:
        query = query.filter(Lead.city == city)
    if remote_type:
        query = query.filter(Lead.remote_type == remote_type)
    if starred_only:
        query = query.filter(Lead.starred.is_(True))
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Lead.title.ilike(like), Lead.company.ilike(like), Lead.signal.ilike(like)))
    return query


def _sorted(query, sort: str):
    if sort == "oldest":
        return query.order_by(Lead.posted_date.asc().nulls_last())
    if sort == "company":
        return query.order_by(Lead.company.asc())
    return query.order_by(Lead.posted_date.desc().nulls_last())  # "newest" (default)


def _lead_to_out(lead: Lead) -> LeadOut:
    data = LeadOut.model_validate(lead)
    data.tags = json.loads(lead.tags_json) if lead.tags_json else []
    return data


@router.get("/leads", response_model=LeadsPage)
def list_leads(
    lead_type: str = "job",
    continent: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    remote_type: Optional[str] = None,
    starred_only: bool = False,
    sort: str = "newest",
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    if lead_type not in ("job", "business"):
        raise HTTPException(status_code=400, detail="lead_type must be 'job' or 'business'")
    query = _apply_filters(db.query(Lead), lead_type, continent, country, city, search, remote_type, starred_only)
    total = query.count()
    query = _sorted(query, sort)
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return LeadsPage(total=total, items=[_lead_to_out(lead) for lead in items])


@router.post("/leads/{lead_id}/star", response_model=LeadOut)
def toggle_star(lead_id: int, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.starred = not lead.starred
    db.commit()
    db.refresh(lead)
    return _lead_to_out(lead)


@router.get("/leads/export")
def export_leads(
    lead_type: str = "job",
    format: str = "csv",
    continent: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    remote_type: Optional[str] = None,
    starred_only: bool = False,
    sort: str = "newest",
    db: Session = Depends(get_db),
):
    query = _apply_filters(db.query(Lead), lead_type, continent, country, city, search, remote_type, starred_only)
    items = _sorted(query, sort).all()
    rows = [_lead_to_out(lead) for lead in items]

    if format == "json":
        payload = json.dumps([row.model_dump(mode="json") for row in rows], indent=2)
        return StreamingResponse(
            io.BytesIO(payload.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=bureau-{lead_type}-leads.json"},
        )

    buffer = io.StringIO()
    fieldnames = list(LeadOut.model_fields.keys())
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        record = row.model_dump(mode="json")
        record["tags"] = ";".join(record.get("tags") or [])
        writer.writerow(record)
    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=bureau-{lead_type}-leads.csv"},
    )


@router.get("/regions")
def get_regions():
    return {"continents": CONTINENTS}


@router.get("/regions/cities")
def get_cities(
    lead_type: str = "job",
    continent: Optional[str] = None,
    country: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Cities are populated dynamically from whatever's actually in the DB,
    not a static list — scoped to the current lead type/continent/country
    filters and an optional search prefix for the autocomplete."""
    query = db.query(Lead.city).filter(Lead.lead_type == lead_type, Lead.city.isnot(None))
    if continent and continent != "Global":
        query = query.filter(Lead.continent == continent)
    if country:
        query = query.filter(Lead.country == country)
    if q:
        query = query.filter(Lead.city.ilike(f"%{q}%"))
    cities = sorted({row[0] for row in query.distinct().limit(500).all() if row[0]})
    return {"cities": cities[:50]}
