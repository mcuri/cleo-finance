import os
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature

from backend.config import get_settings

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

router = APIRouter(prefix="/auth", tags=["auth"])


def _signer():
    return URLSafeTimedSerializer(get_settings().session_secret)


_SESSION_MAX_AGE = 86400 * 30


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


@router.get("/me")
def me(session: dict = Depends(require_auth)):
    return {"email": session["email"]}
