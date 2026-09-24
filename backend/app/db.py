import logging
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
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DB_PATH

logger = logging.getLogger("bureau.db")

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

    # The posting's own text, stored as plain text (never raw HTML — see
    # sources/html_text.py for why). This is what a lead detail view shows
    # and what Sabha decomposes into requirements; without it Sabha would
    # be judging a CV against nothing but a job title.
    description = Column(Text, nullable=True)

    # Cheap local-model screen: a rough 0-100 fit against the stored CV, so
    # the whole feed can be ranked. Explicitly NOT a Sabha verdict.
    fit_score = Column(Integer, nullable=True, index=True)
    fit_reason = Column(Text, nullable=True)
    fit_scored_at = Column(DateTime, nullable=True)

    # The real thing: a full 7-member Sabha council run, on demand only.
    council_status = Column(String, nullable=True)  # running | done | failed
    council_score = Column(Integer, nullable=True)
    council_match_pct = Column(Integer, nullable=True)
    council_json = Column(Text, nullable=True)
    council_run_at = Column(DateTime, nullable=True)

    posted_date = Column(DateTime, nullable=True)
    starred = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


def _add_missing_columns() -> None:
    """SQLAlchemy's create_all() only creates missing *tables*, never missing
    columns, so a model change would otherwise break an existing database (or,
    worse, appear to work until something SELECTs the new column). There are no
    migrations here by design — this is a single-user SQLite tool — so instead
    each new column is ALTERed in on startup if the table predates it. Adding a
    nullable column is the only schema change this supports; anything more
    involved is a rebuild of data/bureau.db."""
    inspector = inspect(engine)
    if "leads" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("leads")}
    wanted = {col.name: col for col in Lead.__table__.columns}

    with engine.begin() as conn:
        for name, column in wanted.items():
            if name in existing:
                continue
            ddl = column.type.compile(engine.dialect)
            conn.execute(text(f"ALTER TABLE leads ADD COLUMN {name} {ddl}"))
            logger.info("added missing column leads.%s (%s)", name, ddl)


def init_db():
    Base.metadata.create_all(engine)
    _add_missing_columns()
