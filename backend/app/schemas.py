from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LeadOut(BaseModel):
    id: int
    lead_type: str
    source: str
    title: str
    company: str
    company_domain: Optional[str] = None
    url: Optional[str] = None

    continent: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None

    remote_type: Optional[str] = None
    seniority: Optional[str] = None

    industry: Optional[str] = None
    contact_path: Optional[str] = None

    company_size: Optional[str] = None
    funding_stage: Optional[str] = None
    signal: Optional[str] = None
    tags: list[str] = []

    # The cheap local screen, carried in list responses so the feed can be
    # ranked and each card can show it. The full Sabha verdict is not here —
    # it's on-demand, and lives on LeadDetail.
    fit_score: Optional[int] = None
    fit_reason: Optional[str] = None
    council_status: Optional[str] = None
    council_score: Optional[int] = None

    posted_date: Optional[datetime] = None
    starred: bool = False

    class Config:
        from_attributes = True


class LeadDetail(LeadOut):
    """What the expanded card shows. Descriptions run to several KB each, so
    they're deliberately excluded from list responses — 30 of them per page
    would be most of the payload for text nobody has opened yet."""

    description: Optional[str] = None
    council_match_pct: Optional[int] = None
    council: Optional[dict] = None


class LeadsPage(BaseModel):
    total: int
    items: list[LeadOut]


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    password: str


class RecoverRequest(BaseModel):
    recovery_phrase: str
    new_password: str
