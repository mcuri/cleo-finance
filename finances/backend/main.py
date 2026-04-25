import io
import os
import logging
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.config import get_settings
from backend.auth import router as auth_router
import backend.auth as _auth_module
from backend.transactions import router as transactions_router
from backend.categories import router as categories_router
from backend.telegram_bot import router as telegram_router
from backend.chat import router as chat_router
from backend.csv_import import parse_csv, csv_rows_to_creates, CsvParseError
from backend.models import Transaction
from backend.sheets import SheetsClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

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
app.include_router(telegram_router)
app.include_router(chat_router, dependencies=[Depends(_require_auth)])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/import/preview", dependencies=[Depends(_require_auth)])
async def import_preview(file: UploadFile = File(...)):
    content = await file.read()
    try:
        rows, errors = parse_csv(io.StringIO(content.decode("utf-8")))
    except CsvParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "valid_rows": [
            {"date": str(r.date), "amount": r.amount, "merchant": r.merchant,
             "category": r.category, "type": r.type}
            for r in rows
        ],
        "errors": [{"row": e.row_number, "reason": e.reason} for e in errors],
    }


@app.post("/api/import/confirm", dependencies=[Depends(_require_auth)])
async def import_confirm(file: UploadFile = File(...)):
    content = await file.read()
    try:
        rows, _ = parse_csv(io.StringIO(content.decode("utf-8")))
    except CsvParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    sheets = SheetsClient(spreadsheet_id=get_settings().google_sheets_id)
    count = 0
    for create in csv_rows_to_creates(rows):
        t = Transaction.from_create(create, source="csv")
        sheets.append_transaction(t)
        count += 1
    return {"imported": count}


_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
