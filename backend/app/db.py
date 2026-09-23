from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external_id"),)

    id = Column(Integer, primary_key=True)
    lead_type = Column(String, nullable=False, index=True)  # "job" | "business"
    source = Column(String, nullable=False, index=True)
    external_id = Column(String, nullable=False)

    title = Column(String, nullable=False)
    company = Column(String, nullable=False, index=True)
    company_domain = Column(String, nullable=True)
    url = Column(String, nullable=True)

    continent = Column(String, nullable=True, index=True)
    country = Column(String, nullable=True, index=True)
    city = Column(String, nullable=True, index=True)

    # job-only
    remote_type = Column(String, nullable=True)  # remote | hybrid | onsite
    seniority = Column(String, nullable=True)

    # business-only
    industry = Column(String, nullable=True)
    contact_path = Column(String, nullable=True)

    company_size = Column(String, nullable=True)
    funding_stage = Column(String, nullable=True)
    signal = Column(Text, nullable=True)
    tags_json = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)

    posted_date = Column(DateTime, nullable=True)
    starred = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(engine)
