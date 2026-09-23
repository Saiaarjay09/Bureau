from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth import (
    create_account,
    credentials_configured,
    make_session_cookie,
    require_session,
    reset_password_with_recovery,
    verify_credentials,
)
from ..config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from ..rate_limit import record_failure, record_success, seconds_until_retry
from ..schemas import LoginRequest, RecoverRequest, SignupRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, username: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        make_session_cookie(username),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _enforce_throttle(key: str) -> None:
    wait = seconds_until_retry(key)
    if wait:
        raise HTTPException(status_code=429, detail=f"Too many attempts — try again in {wait}s")


@router.get("/status")
def status():
    return {"credentials_configured": credentials_configured()}


@router.post("/signup")
def signup(body: SignupRequest, response: Response):
    if credentials_configured():
        raise HTTPException(status_code=409, detail="An account already exists")
    if not body.username.strip() or len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Username is required and password must be at least 8 characters")
    recovery_phrase = create_account(body.username.strip(), body.password)
    _set_session_cookie(response, body.username.strip())
    return {"username": body.username.strip(), "recovery_phrase": recovery_phrase}


@router.post("/login")
def login(body: LoginRequest, response: Response, request: Request):
    key = _client_key(request)
    _enforce_throttle(key)
    if not verify_credentials(body.username, body.password):
        record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    record_success(key)
    _set_session_cookie(response, body.username)
    return {"username": body.username}


@router.post("/recover")
def recover(body: RecoverRequest, request: Request):
    key = _client_key(request)
    _enforce_throttle(key)
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not reset_password_with_recovery(body.recovery_phrase, body.new_password):
        record_failure(key)
        raise HTTPException(status_code=400, detail="That recovery phrase doesn't match")
    record_success(key)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(username: str = Depends(require_session)):
    return {"username": username}
