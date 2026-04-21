import os
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from itsdangerous import URLSafeTimedSerializer, BadSignature

from backend.config import get_settings

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

router = APIRouter(prefix="/auth", tags=["auth"])

_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
_SESSION_MAX_AGE = 86400 * 30  # 30 days


def _signer():
    return URLSafeTimedSerializer(get_settings().session_secret)


def _make_flow() -> Flow:
    settings = get_settings()
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=_SCOPES,
        redirect_uri=f"{settings.app_url}/auth/callback",
    )


def _set_session(response: Response, email: str) -> None:
    token = _signer().dumps({"email": email})
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=_SESSION_MAX_AGE
    )


def _read_session(request: Request) -> Optional[dict]:
    raw = request.cookies.get("session")
    if not raw:
        return None
    try:
        return _signer().loads(raw, max_age=_SESSION_MAX_AGE)
    except BadSignature:
        return None


def require_auth(request: Request) -> dict:
    session = _read_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


@router.get("/login")
def login():
    flow = _make_flow()
    auth_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(auth_url)


@router.get("/callback")
def callback(request: Request, code: str):
    flow = _make_flow()
    flow.fetch_token(code=code)
    info = id_token.verify_oauth2_token(
        flow.credentials.id_token,
        google_requests.Request(),
        get_settings().google_client_id,
    )
    email = info.get("email", "")
    if email != get_settings().allowed_email:
        raise HTTPException(status_code=403, detail="Access denied")
    response = RedirectResponse(url="/")
    _set_session(response, email)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/login")
    response.delete_cookie("session")
    return response


@router.get("/me")
def me(session: dict = Depends(require_auth)):
    return {"email": session["email"]}
