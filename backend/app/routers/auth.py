from fastapi import APIRouter, Depends, HTTPException, Response

from ..auth import (
    credentials_configured,
    make_session_cookie,
    require_session,
    verify_credentials,
)
from ..config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from ..schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
def status():
    return {"credentials_configured": credentials_configured()}


@router.post("/login")
def login(body: LoginRequest, response: Response):
    if not verify_credentials(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = make_session_cookie(body.username)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return {"username": body.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(username: str = Depends(require_session)):
    return {"username": username}
