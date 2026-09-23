"""Single-user session auth: username + bcrypt-hashed password, signed cookie session.

Credentials live in data/auth.json (bcrypt hash, never plaintext), managed via
scripts/set_password.py rather than being hardcoded anywhere.
"""

import json

import bcrypt
from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import AUTH_PATH, SECRET_KEY, SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS

serializer = URLSafeTimedSerializer(SECRET_KEY, salt="scout-session")


def credentials_configured() -> bool:
    return AUTH_PATH.exists()


def set_credentials(username: str, password: str) -> None:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    AUTH_PATH.write_text(json.dumps({"username": username, "password_hash": password_hash}))


def verify_credentials(username: str, password: str) -> bool:
    if not credentials_configured():
        return False
    data = json.loads(AUTH_PATH.read_text())
    if username != data["username"]:
        return False
    return bcrypt.checkpw(password.encode(), data["password_hash"].encode())


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
    return username
