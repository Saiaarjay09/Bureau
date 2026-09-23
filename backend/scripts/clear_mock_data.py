#!/usr/bin/env python3
"""Remove mock leads once real sources have populated enough data to not need them."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Lead, SessionLocal  # noqa: E402


def main():
    db = SessionLocal()
    try:
        n = db.query(Lead).filter(Lead.source == "mock").delete()
        db.commit()
        print(f"Removed {n} mock leads.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
