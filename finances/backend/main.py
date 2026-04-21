from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.auth import router as auth_router
import backend.auth as _auth_module
from backend.transactions import router as transactions_router
from backend.categories import router as categories_router

app = FastAPI(title="Finance Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_auth(request: Request):
    return _auth_module.require_auth(request)


app.include_router(auth_router)
app.include_router(transactions_router, dependencies=[Depends(_require_auth)])
app.include_router(categories_router, dependencies=[Depends(_require_auth)])


@app.get("/health")
def health():
    return {"status": "ok"}
