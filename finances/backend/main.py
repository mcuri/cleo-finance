import os
import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.config import get_settings
from backend.auth import router as auth_router
import backend.auth as _auth_module
from backend.transactions import router as transactions_router
from backend.categories import router as categories_router
from backend.telegram_bot import router as telegram_router
from backend.chat import router as chat_router
from backend.models import Transaction
from backend.sheets import SheetsClient
import backend.scheduler as _scheduler

# Set up file logging for the app
logs_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, "app.log")

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
file_handler = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    _scheduler.start()
    yield
    _scheduler.stop()


app = FastAPI(title="Finance Tracker", lifespan=lifespan)

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
app.include_router(telegram_router)
app.include_router(chat_router, dependencies=[Depends(_require_auth)])


@app.get("/health")
def health():
    return {"status": "ok"}


_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
