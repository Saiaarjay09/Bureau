"""Single-user session auth: username + bcrypt-hashed password, signed
cookie session, plus a one-time recovery phrase for password resets.

Credentials live in data/auth.json — password and recovery-phrase hashes
only, never plaintext. The normal path to create an account is the web
UI's first-run signup screen (POST /api/auth/signup), which is what
generates and returns the recovery phrase; scripts/set_password.py is an
emergency CLI escape hatch that bypasses recovery entirely, for when
you've lost both the password and the phrase.
"""

import json

import bcrypt
from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import AUTH_PATH, SECRET_KEY, SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from .recovery import generate_recovery_phrase, normalize_phrase

serializer = URLSafeTimedSerializer(SECRET_KEY, salt="bureau-session")


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def _check(secret: str, hashed: str) -> bool:
    return bcrypt.checkpw(secret.encode(), hashed.encode())


def credentials_configured() -> bool:
    return AUTH_PATH.exists()


def _read() -> dict | None:
    if not AUTH_PATH.exists():
        return None
    return json.loads(AUTH_PATH.read_text())


def _write(data: dict) -> None:
    AUTH_PATH.write_text(json.dumps(data))


def create_account(username: str, password: str) -> str:
    """First-time signup. Generates and returns a fresh recovery phrase —
    the only time it's ever available in plaintext, so the caller must
    show it to the user immediately. Raises ValueError if an account
    already exists (Bureau is single-user; signup is a one-time thing)."""
    if credentials_configured():
        raise ValueError("An account already exists")
    phrase = generate_recovery_phrase()
    _write({
        "username": username,
        "password_hash": _hash(password),
        "recovery_phrase_hash": _hash(normalize_phrase(phrase)),
    })
    return phrase


def set_credentials(username: str, password: str) -> None:
    """CLI-only escape hatch (scripts/set_password.py): force-set the
    password without touching any existing recovery phrase. On a brand
    new install this creates an account with no recovery phrase at all —
    use the web signup flow instead if you want one."""
    data = _read() or {"recovery_phrase_hash": None}
    data["username"] = username
    data["password_hash"] = _hash(password)
    _write(data)


def verify_credentials(username: str, password: str) -> bool:
    data = _read()
    if not data or username != data["username"]:
        return False
    return _check(password, data["password_hash"])


def verify_recovery_phrase(phrase: str) -> bool:
    data = _read()
    if not data or not data.get("recovery_phrase_hash"):
        return False
    return _check(normalize_phrase(phrase), data["recovery_phrase_hash"])


def reset_password_with_recovery(phrase: str, new_password: str) -> bool:
    if not verify_recovery_phrase(phrase):
        return False
    data = _read()
    data["password_hash"] = _hash(new_password)
    _write(data)
    return True


def make_session_cookie(username: str) -> str:
    return serializer.dumps({"u": username})


def read_session_cookie(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except BadSignature:
        return None
    return data.get("u")


def require_session(request: Request) -> str:
    username = read_session_cookie(request)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # A signature check alone isn't enough: if the account was recreated
    # (or its username changed) since this cookie was issued, the old
    # cookie would otherwise still authenticate as a no-longer-current
    # account. Cross-check against the account record every request.
    data = _read()
    if not data or data.get("username") != username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username
