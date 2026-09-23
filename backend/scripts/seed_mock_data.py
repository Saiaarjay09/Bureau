#!/usr/bin/env python3
"""Seed the DB with mock leads for previewing the UI. Safe to re-run (upserts)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, init_db  # noqa: E402
from app.ingest import upsert_leads  # noqa: E402
from app.mock_data import mock_businesses, mock_jobs  # noqa: E402


def main():
    init_db()
    db = SessionLocal()
    try:
        created, updated = upsert_leads(db, mock_jobs() + mock_businesses())
        print(f"Seeded mock data: {created} created, {updated} updated.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
