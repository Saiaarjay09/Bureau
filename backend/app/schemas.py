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

    posted_date: Optional[datetime] = None
    starred: bool = False

    class Config:
        from_attributes = True


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
