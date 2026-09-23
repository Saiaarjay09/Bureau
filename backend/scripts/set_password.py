#!/usr/bin/env python3
"""Set or change the Scout login credentials.

Usage:
    python3 scripts/set_password.py
    python3 scripts/set_password.py --username saideep --password 'hunter2'   # non-interactive

Password is stored as a bcrypt hash in backend/data/auth.json — never plaintext.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import set_credentials  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username")
    parser.add_argument("--password")
    args = parser.parse_args()

    username = args.username or input("Username: ").strip()
    password = args.password or getpass.getpass("Password: ")
    if not username or not password:
        print("Username and password are both required.", file=sys.stderr)
        sys.exit(1)

    set_credentials(username, password)
    print(f"Credentials set for '{username}'.")


if __name__ == "__main__":
    main()
