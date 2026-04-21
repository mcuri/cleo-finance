# Personal Finance App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal cash flow tracker with a FastAPI backend, React frontend, Google Sheets as data store, Google OAuth authentication, and a Telegram bot for receipt/text expense logging.

**Architecture:** Single FastAPI backend serves both REST API (consumed by the React SPA) and a Telegram webhook. All data is persisted to a single Google Spreadsheet via the Sheets API (service account). Google OAuth protects all routes — only the owner's email can access the app. Claude Haiku parses receipt photos and natural language expense text from Telegram.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, itsdangerous, pydantic-settings, google-api-python-client, google-auth-oauthlib, anthropic, python-telegram-bot 21+, React 18, TypeScript, Vite, Recharts, react-router-dom, pytest, httpx

---

## Prerequisites (manual — do before Task 1)

1. **Google Cloud project:** Enable the Sheets API and the Google+ / OpenID API.
2. **Service account:** Create one, download the JSON key → save as `backend/service-account.json`.
3. **Google Spreadsheet:** Create a new spreadsheet. Note its ID (from the URL). Share it with the service account email (Editor).  Add two sheets named exactly `Transactions` and `Categories`.
4. **OAuth2 credentials:** Create OAuth2 "Web application" credentials. Add `http://localhost:8000/auth/callback` as an authorised redirect URI. Note the client ID and secret.
5. **Telegram bot:** Message @BotFather → `/newbot`. Note the token.
6. **Anthropic API key:** From console.anthropic.com.

---

## File Structure

```
finances/
├── backend/
│   ├── main.py              # FastAPI app, router registration, CORS
│   ├── config.py            # Settings from .env via pydantic-settings
│   ├── auth.py              # Google OAuth2 flow + signed-cookie session
│   ├── models.py            # Pydantic models: Transaction, Category, ParsedExpense
│   ├── sheets.py            # Google Sheets read/write (service account)
│   ├── transactions.py      # /api/transactions CRUD router
│   ├── categories.py        # /api/categories router
│   ├── csv_import.py        # CSV parsing + bulk insert logic
│   ├── claude_parser.py     # Claude API: receipt image + NL text parsing
│   ├── telegram_bot.py      # /webhook Telegram handler
│   ├── init_sheets.py       # One-time script: headers + predefined categories
│   └── service-account.json # (gitignored) service account credentials
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_sheets.py
│   ├── test_transactions.py
│   ├── test_csv_import.py
│   └── test_claude_parser.py
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx          # Route definitions
│   │   ├── index.css        # Mobile-first global styles
│   │   ├── api.ts           # Typed API client
│   │   ├── types.ts         # Shared TypeScript types
│   │   └── components/
│   │       ├── Dashboard.tsx
│   │       ├── TransactionList.tsx
│   │       ├── AddTransaction.tsx
│   │       ├── CsvImport.tsx
│   │       └── CategoryManager.tsx
│   ├── package.json
│   └── vite.config.ts
├── register_webhook.py      # One-time script: register Telegram webhook
├── .env                     # (gitignored)
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/config.py`
- Create: `backend/main.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
itsdangerous==2.2.0
pydantic-settings==2.3.4
python-dotenv==1.0.1
google-api-python-client==2.136.0
google-auth==2.31.0
google-auth-oauthlib==1.2.1
anthropic==0.30.0
python-telegram-bot==21.4
python-multipart==0.0.9
pytest==8.2.2
pytest-asyncio==0.23.7
httpx==0.27.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install without errors.

- [ ] **Step 3: Create .env.example**

```
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
GOOGLE_SHEETS_ID=your-spreadsheet-id
SESSION_SECRET=change-me-to-a-random-string
ALLOWED_EMAIL=your@gmail.com
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_WEBHOOK_SECRET=change-me-to-a-random-string
ANTHROPIC_API_KEY=your-anthropic-api-key
APP_URL=http://localhost:8000
```

Copy to `.env` and fill in real values.

- [ ] **Step 4: Create .gitignore**

```
.env
backend/service-account.json
__pycache__/
*.pyc
.pytest_cache/
node_modules/
frontend/dist/
```

- [ ] **Step 5: Create backend/config.py**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    google_client_id: str
    google_client_secret: str
    google_sheets_id: str
    session_secret: str
    allowed_email: str
    telegram_bot_token: str
    telegram_webhook_secret: str
    anthropic_api_key: str
    app_url: str = "http://localhost:8000"

    model_config = {"env_file": ".env"}

settings = Settings()
```

- [ ] **Step 6: Create backend/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Finance Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Create tests/conftest.py**

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 8: Verify server starts**

Run: `uvicorn backend.main:app --reload`
Expected: Server starts at http://127.0.0.1:8000. `curl http://localhost:8000/health` returns `{"status":"ok"}`.

- [ ] **Step 9: Commit**

```bash
git init
git add requirements.txt .env.example .gitignore backend/main.py backend/config.py tests/conftest.py
git commit -m "feat: project scaffold"
```

---

## Task 2: Pydantic models

**Files:**
- Create: `backend/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py
from datetime import date
import pytest
from backend.models import Transaction, TransactionCreate, Category, ParsedExpense

def test_transaction_create_valid():
    t = TransactionCreate(
        date=date(2026, 4, 20),
        amount=47.50,
        merchant="Trader Joe's",
        category="Groceries",
        type="expense",
    )
    assert t.amount == 47.50

def test_transaction_create_negative_amount_raises():
    with pytest.raises(ValueError):
        TransactionCreate(
            date=date(2026, 4, 20),
            amount=-10.0,
            merchant="Test",
            category="Other",
            type="expense",
        )

def test_category_name_stripped():
    c = Category(name="  Groceries  ", predefined=False)
    assert c.name == "Groceries"

def test_parsed_expense_optional_fields():
    p = ParsedExpense(amount=100.0, merchant="Starbucks", category="Restaurants")
    assert p.date is None
    assert p.notes is None

def test_transaction_from_create_sets_id_and_source():
    create = TransactionCreate(
        date=date(2026, 4, 20),
        amount=50.0,
        merchant="Target",
        category="Shopping",
        type="expense",
    )
    t = Transaction.from_create(create, source="web")
    assert t.source == "web"
    assert len(t.id) > 0
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `pytest tests/test_models.py -v`
Expected: `ModuleNotFoundError` — `backend.models` does not exist.

- [ ] **Step 3: Create backend/models.py**

```python
from pydantic import BaseModel, field_validator
from datetime import date
from typing import Literal, Optional
import uuid

TransactionType = Literal["income", "expense"]
TransactionSource = Literal["web", "csv", "telegram"]


class TransactionCreate(BaseModel):
    date: date
    amount: float
    merchant: str
    category: str
    type: TransactionType
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class Transaction(TransactionCreate):
    id: str
    source: TransactionSource

    @classmethod
    def from_create(cls, data: TransactionCreate, source: TransactionSource) -> "Transaction":
        return cls(**data.model_dump(), id=str(uuid.uuid4()), source=source)


class Category(BaseModel):
    name: str
    predefined: bool

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class ParsedExpense(BaseModel):
    amount: float
    merchant: str
    category: str
    date: Optional[date] = None
    notes: Optional[str] = None
    confidence: float = 1.0
```

- [ ] **Step 4: Run tests — confirm they pass**

Run: `pytest tests/test_models.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py tests/test_models.py
git commit -m "feat: Pydantic models for transactions, categories, parsed expenses"
```

---

## Task 3: Google Sheets client

**Files:**
- Create: `backend/sheets.py`
- Create: `backend/init_sheets.py`
- Create: `tests/test_sheets.py`

Spreadsheet layout:
- `Transactions` sheet: columns A–H → `id, date, amount, merchant, category, type, source, notes` (row 1 = header)
- `Categories` sheet: columns A–B → `name, predefined` (row 1 = header; `predefined` is `"TRUE"` or `"FALSE"`)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sheets.py
from unittest.mock import MagicMock, patch
from datetime import date
import pytest
from backend.models import Transaction, Category

FAKE_ID = "fake-spreadsheet-id"

@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.spreadsheets().get().execute.return_value = {
        "sheets": [
            {"properties": {"title": "Transactions", "sheetId": 0}},
            {"properties": {"title": "Categories", "sheetId": 1}},
        ]
    }
    return svc

@pytest.fixture
def sheets_client(mock_service):
    from backend.sheets import SheetsClient
    client = SheetsClient.__new__(SheetsClient)
    client.spreadsheet_id = FAKE_ID
    client._service = mock_service
    return client

def test_append_transaction(sheets_client, mock_service):
    t = Transaction(
        id="abc123",
        date=date(2026, 4, 20),
        amount=47.50,
        merchant="Trader Joe's",
        category="Groceries",
        type="expense",
        source="web",
    )
    sheets_client.append_transaction(t)
    mock_service.spreadsheets().values().append.assert_called_once()
    kwargs = mock_service.spreadsheets().values().append.call_args[1]
    row = kwargs["body"]["values"][0]
    assert row[0] == "abc123"
    assert row[2] == 47.50

def test_get_all_transactions_empty(sheets_client, mock_service):
    mock_service.spreadsheets().values().get().execute.return_value = {"values": []}
    from backend.sheets import SheetsClient
    result = sheets_client.get_all_transactions()
    assert result == []

def test_get_categories(sheets_client, mock_service):
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [
            ["Groceries", "TRUE"],
            ["My Custom", "FALSE"],
        ]
    }
    from backend.sheets import SheetsClient
    cats = sheets_client.get_categories()
    assert len(cats) == 2
    assert cats[0].name == "Groceries"
    assert cats[0].predefined is True
    assert cats[1].predefined is False
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `pytest tests/test_sheets.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create backend/sheets.py**

```python
import os
from typing import List, Optional
from datetime import date as date_type

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

from backend.models import Transaction, Category, TransactionSource

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service-account.json")


def build_service():
    creds = Credentials.from_service_account_file(_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


class SheetsClient:
    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self._service = build_service()

    def _values(self):
        return self._service.spreadsheets().values()

    def _get_sheet_id(self, sheet_name: str) -> int:
        meta = self._service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id
        ).execute()
        for sheet in meta["sheets"]:
            if sheet["properties"]["title"] == sheet_name:
                return sheet["properties"]["sheetId"]
        raise ValueError(f"Sheet '{sheet_name}' not found")

    # ── Transactions ────────────────────────────────────────────────────────

    def append_transaction(self, t: Transaction) -> None:
        row = [
            t.id,
            t.date.isoformat(),
            t.amount,
            t.merchant,
            t.category,
            t.type,
            t.source,
            t.notes or "",
        ]
        self._values().append(
            spreadsheetId=self.spreadsheet_id,
            range="Transactions!A:H",
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()

    def get_all_transactions(self) -> List[Transaction]:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Transactions!A2:H",
        ).execute()
        rows = result.get("values", [])
        transactions = []
        for row in rows:
            if len(row) < 7:
                continue
            transactions.append(Transaction(
                id=row[0],
                date=date_type.fromisoformat(row[1]),
                amount=float(row[2]),
                merchant=row[3],
                category=row[4],
                type=row[5],
                source=row[6],
                notes=row[7] if len(row) > 7 and row[7] else None,
            ))
        return transactions

    def delete_transaction(self, transaction_id: str) -> bool:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Transactions!A:A",
        ).execute()
        rows = result.get("values", [])
        for idx, row in enumerate(rows):
            if row and row[0] == transaction_id:
                sheet_id = self._get_sheet_id("Transactions")
                self._service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={"requests": [{"deleteDimension": {"range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": idx,
                        "endIndex": idx + 1,
                    }}}]},
                ).execute()
                return True
        return False

    def find_duplicate(self, date: date_type, amount: float, merchant: str) -> bool:
        transactions = self.get_all_transactions()
        for t in transactions:
            if t.date == date and t.amount == amount and t.merchant.lower() == merchant.lower():
                return True
        return False

    # ── Categories ──────────────────────────────────────────────────────────

    def get_categories(self) -> List[Category]:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Categories!A2:B",
        ).execute()
        rows = result.get("values", [])
        return [
            Category(name=row[0], predefined=(row[1].upper() == "TRUE"))
            for row in rows
            if len(row) >= 2
        ]

    def append_category(self, name: str) -> None:
        self._values().append(
            spreadsheetId=self.spreadsheet_id,
            range="Categories!A:B",
            valueInputOption="RAW",
            body={"values": [[name, "FALSE"]]},
        ).execute()

    def delete_category(self, name: str) -> bool:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Categories!A:A",
        ).execute()
        rows = result.get("values", [])
        for idx, row in enumerate(rows):
            if row and row[0] == name:
                sheet_id = self._get_sheet_id("Categories")
                self._service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={"requests": [{"deleteDimension": {"range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": idx,
                        "endIndex": idx + 1,
                    }}}]},
                ).execute()
                return True
        return False
```

- [ ] **Step 4: Run tests — confirm they pass**

Run: `pytest tests/test_sheets.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Create backend/init_sheets.py**

Run this once to set up headers and predefined categories in the spreadsheet.

```python
# backend/init_sheets.py
from backend.sheets import build_service
from backend.config import settings

PREDEFINED = [
    "Utilities", "Groceries", "Restaurants", "Transport",
    "Entertainment", "Health", "Shopping", "Travel", "Income", "Other",
]

def init():
    svc = build_service()
    vals = svc.spreadsheets().values()

    vals.update(
        spreadsheetId=settings.google_sheets_id,
        range="Transactions!A1:H1",
        valueInputOption="RAW",
        body={"values": [["id", "date", "amount", "merchant", "category", "type", "source", "notes"]]},
    ).execute()

    rows = [["name", "predefined"]] + [[c, "TRUE"] for c in PREDEFINED]
    vals.update(
        spreadsheetId=settings.google_sheets_id,
        range=f"Categories!A1:B{len(rows)}",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()
    print("Sheets initialised.")

if __name__ == "__main__":
    init()
```

Run: `python -m backend.init_sheets`
Expected: `Sheets initialised.` — open the spreadsheet to verify headers and categories exist.

- [ ] **Step 6: Commit**

```bash
git add backend/sheets.py backend/init_sheets.py tests/test_sheets.py
git commit -m "feat: Google Sheets client with transaction and category CRUD"
```

---

## Task 4: Transactions and Categories API

**Files:**
- Create: `backend/transactions.py`
- Create: `backend/categories.py`
- Modify: `backend/main.py`
- Create: `tests/test_transactions.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_transactions.py
from unittest.mock import MagicMock, patch
from datetime import date
import pytest
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture
def mock_sheets():
    return MagicMock()

@pytest.fixture
def client(mock_sheets):
    with patch("backend.transactions.get_sheets_client", return_value=mock_sheets), \
         patch("backend.categories.get_sheets_client", return_value=mock_sheets), \
         patch("backend.auth.require_auth", return_value={"email": "test@test.com"}):
        yield TestClient(app)

def test_list_transactions_empty(client, mock_sheets):
    mock_sheets.get_all_transactions.return_value = []
    resp = client.get("/api/transactions")
    assert resp.status_code == 200
    assert resp.json() == []

def test_create_transaction(client, mock_sheets):
    mock_sheets.find_duplicate.return_value = False
    mock_sheets.append_transaction.return_value = None
    resp = client.post("/api/transactions", json={
        "date": "2026-04-20",
        "amount": 47.50,
        "merchant": "Trader Joe's",
        "category": "Groceries",
        "type": "expense",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["merchant"] == "Trader Joe's"
    assert data["source"] == "web"
    assert "id" in data

def test_create_transaction_duplicate_warns(client, mock_sheets):
    mock_sheets.find_duplicate.return_value = True
    resp = client.post("/api/transactions", json={
        "date": "2026-04-20",
        "amount": 47.50,
        "merchant": "Trader Joe's",
        "category": "Groceries",
        "type": "expense",
    })
    assert resp.status_code == 409

def test_delete_transaction(client, mock_sheets):
    mock_sheets.delete_transaction.return_value = True
    resp = client.delete("/api/transactions/abc123")
    assert resp.status_code == 204

def test_delete_transaction_not_found(client, mock_sheets):
    mock_sheets.delete_transaction.return_value = False
    resp = client.delete("/api/transactions/notexist")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `pytest tests/test_transactions.py -v`
Expected: `ModuleNotFoundError` or import failures.

- [ ] **Step 3: Create backend/transactions.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from backend.models import Transaction, TransactionCreate
from backend.sheets import SheetsClient
from backend.config import settings

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=settings.google_sheets_id)


@router.get("", response_model=List[Transaction])
def list_transactions(sheets: SheetsClient = Depends(get_sheets_client)):
    return sheets.get_all_transactions()


@router.post("", response_model=Transaction, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionCreate,
    sheets: SheetsClient = Depends(get_sheets_client),
):
    if sheets.find_duplicate(data.date, data.amount, data.merchant):
        raise HTTPException(
            status_code=409,
            detail="A transaction with the same date, amount, and merchant already exists.",
        )
    transaction = Transaction.from_create(data, source="web")
    sheets.append_transaction(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: str,
    sheets: SheetsClient = Depends(get_sheets_client),
):
    if not sheets.delete_transaction(transaction_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
```

- [ ] **Step 4: Create backend/categories.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from pydantic import BaseModel

from backend.models import Category
from backend.sheets import SheetsClient
from backend.config import settings

router = APIRouter(prefix="/api/categories", tags=["categories"])


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=settings.google_sheets_id)


class CategoryCreate(BaseModel):
    name: str


@router.get("", response_model=List[Category])
def list_categories(sheets: SheetsClient = Depends(get_sheets_client)):
    return sheets.get_categories()


@router.post("", response_model=Category, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, sheets: SheetsClient = Depends(get_sheets_client)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name required")
    sheets.append_category(name)
    return Category(name=name, predefined=False)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(name: str, sheets: SheetsClient = Depends(get_sheets_client)):
    if not sheets.delete_category(name):
        raise HTTPException(status_code=404, detail="Category not found")
```

- [ ] **Step 5: Update backend/main.py to register routers**

```python
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from backend.transactions import router as transactions_router
from backend.categories import router as categories_router

app = FastAPI(title="Finance Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions_router)
app.include_router(categories_router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

Note: auth dependency will be added in Task 5 once `backend/auth.py` exists.

- [ ] **Step 6: Run tests — confirm they pass**

Run: `pytest tests/test_transactions.py -v`
Expected: 5 tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/transactions.py backend/categories.py backend/main.py tests/test_transactions.py
git commit -m "feat: transactions and categories REST API with duplicate detection"
```

---

## Task 5: Google OAuth authentication

**Files:**
- Create: `backend/auth.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create backend/auth.py**

```python
import os
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from itsdangerous import URLSafeTimedSerializer, BadSignature

from backend.config import settings

# Allow HTTP for local dev. Remove this line in production (use HTTPS).
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

router = APIRouter(prefix="/auth", tags=["auth"])
_signer = URLSafeTimedSerializer(settings.session_secret)

_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
_SESSION_MAX_AGE = 86400 * 30  # 30 days


def _make_flow() -> Flow:
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
    token = _signer.dumps({"email": email})
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=_SESSION_MAX_AGE
    )


def _read_session(request: Request) -> dict | None:
    raw = request.cookies.get("session")
    if not raw:
        return None
    try:
        return _signer.loads(raw, max_age=_SESSION_MAX_AGE)
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
        settings.google_client_id,
    )
    email = info.get("email", "")
    if email != settings.allowed_email:
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
```

- [ ] **Step 2: Update backend/main.py to register auth and protect API routes**

```python
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from backend.auth import router as auth_router, require_auth
from backend.transactions import router as transactions_router
from backend.categories import router as categories_router

app = FastAPI(title="Finance Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(transactions_router, dependencies=[Depends(require_auth)])
app.include_router(categories_router, dependencies=[Depends(require_auth)])

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Test the auth flow manually**

Run: `uvicorn backend.main:app --reload`
Open: http://localhost:8000/auth/login
Expected: Redirects to Google sign-in. After signing in with `ALLOWED_EMAIL`, redirects to `/`. `GET /auth/me` returns `{"email": "your@gmail.com"}`.

- [ ] **Step 4: Verify unauthorized access returns 401**

Run (no cookie): `curl http://localhost:8000/api/transactions`
Expected: `{"detail":"Not authenticated"}`

- [ ] **Step 5: Verify wrong account returns 403**

Sign in with a different Google account.
Expected: `{"detail":"Access denied"}`

- [ ] **Step 6: Commit**

```bash
git add backend/auth.py backend/main.py
git commit -m "feat: Google OAuth2 authentication with email whitelist and session cookie"
```

---

## Task 6: CSV import

**Files:**
- Create: `backend/csv_import.py`
- Modify: `backend/main.py`
- Create: `tests/test_csv_import.py`

CSV format: header row required. Columns: `date` (YYYY-MM-DD), `amount` (positive number), `merchant` (string), `category` (string), `type` (`income` or `expense`). Extra columns are ignored.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_csv_import.py
import io
import pytest
from backend.csv_import import parse_csv, CsvParseError, CsvRowError

VALID_CSV = """date,amount,merchant,category,type
2026-04-01,47.50,Trader Joe's,Groceries,expense
2026-04-02,3000.00,Employer,Income,income
"""

BAD_AMOUNT_CSV = """date,amount,merchant,category,type
2026-04-01,not-a-number,Trader Joe's,Groceries,expense
2026-04-02,3000.00,Employer,Income,income
"""

MISSING_COLUMNS_CSV = """date,amount,merchant
2026-04-01,47.50,Trader Joe's
"""

def test_parse_valid_csv():
    rows, errors = parse_csv(io.StringIO(VALID_CSV))
    assert len(rows) == 2
    assert rows[0].merchant == "Trader Joe's"
    assert rows[0].amount == 47.50
    assert len(errors) == 0

def test_parse_bad_amount_row_becomes_error():
    rows, errors = parse_csv(io.StringIO(BAD_AMOUNT_CSV))
    assert len(rows) == 1
    assert len(errors) == 1
    assert errors[0].row_number == 2

def test_parse_missing_required_column_raises():
    with pytest.raises(CsvParseError):
        parse_csv(io.StringIO(MISSING_COLUMNS_CSV))
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `pytest tests/test_csv_import.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create backend/csv_import.py**

```python
import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import IO, List, Tuple

from backend.models import TransactionCreate

REQUIRED_COLUMNS = {"date", "amount", "merchant", "category", "type"}


class CsvParseError(Exception):
    pass


@dataclass
class CsvRowError:
    row_number: int
    reason: str


@dataclass
class CsvRow:
    date: date
    amount: float
    merchant: str
    category: str
    type: str


def parse_csv(file: IO[str]) -> Tuple[List[CsvRow], List[CsvRowError]]:
    reader = csv.DictReader(file)
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CsvParseError(f"Missing required columns: {missing}")

    rows: List[CsvRow] = []
    errors: List[CsvRowError] = []

    for i, raw in enumerate(reader, start=2):
        try:
            rows.append(CsvRow(
                date=date.fromisoformat(raw["date"].strip()),
                amount=float(raw["amount"].strip()),
                merchant=raw["merchant"].strip(),
                category=raw["category"].strip(),
                type=raw["type"].strip().lower(),
            ))
        except (ValueError, KeyError) as exc:
            errors.append(CsvRowError(row_number=i, reason=str(exc)))

    return rows, errors


def csv_rows_to_creates(rows: List[CsvRow]) -> List[TransactionCreate]:
    return [
        TransactionCreate(
            date=row.date,
            amount=row.amount,
            merchant=row.merchant,
            category=row.category,
            type=row.type,
        )
        for row in rows
    ]
```

- [ ] **Step 4: Run tests — confirm they pass**

Run: `pytest tests/test_csv_import.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Add import endpoints to backend/main.py**

Add the following imports and routes at the bottom of `backend/main.py`:

```python
import io
from fastapi import UploadFile, File
from backend.csv_import import parse_csv, csv_rows_to_creates, CsvParseError
from backend.models import Transaction
from backend.sheets import SheetsClient
from backend.config import settings


@app.post("/api/import/preview", dependencies=[Depends(require_auth)])
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


@app.post("/api/import/confirm", dependencies=[Depends(require_auth)])
async def import_confirm(file: UploadFile = File(...)):
    content = await file.read()
    try:
        rows, _ = parse_csv(io.StringIO(content.decode("utf-8")))
    except CsvParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    sheets = SheetsClient(spreadsheet_id=settings.google_sheets_id)
    count = 0
    for create in csv_rows_to_creates(rows):
        t = Transaction.from_create(create, source="csv")
        sheets.append_transaction(t)
        count += 1
    return {"imported": count}
```

Also add `HTTPException` to the existing FastAPI import at the top of main.py:

```python
from fastapi import FastAPI, Depends, HTTPException
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/csv_import.py backend/main.py tests/test_csv_import.py
git commit -m "feat: CSV import with preview and confirm endpoints"
```

---

## Task 7: Claude parser

**Files:**
- Create: `backend/claude_parser.py`
- Create: `tests/test_claude_parser.py`

Uses `claude-haiku-4-5-20251001` (fast and cheap) for both text parsing and receipt OCR.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_claude_parser.py
from unittest.mock import MagicMock, patch
import pytest
from backend.claude_parser import parse_expense_text, parse_receipt_image

def _mock_response(text: str):
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock

VALID_JSON = '{"amount": 100.0, "merchant": "Trader Joe\'s", "category": "Groceries", "date": "2026-04-20", "confidence": 0.95}'

def test_parse_expense_text_returns_parsed_expense():
    with patch("backend.claude_parser._client") as mock_client:
        mock_client.messages.create.return_value = _mock_response(VALID_JSON)
        result = parse_expense_text("I spent $100 at Trader Joe's on groceries")
    assert result is not None
    assert result.amount == 100.0
    assert result.merchant == "Trader Joe's"
    assert result.confidence == 0.95

def test_parse_expense_text_malformed_json_returns_none():
    with patch("backend.claude_parser._client") as mock_client:
        mock_client.messages.create.return_value = _mock_response("not valid json at all")
        result = parse_expense_text("gibberish")
    assert result is None

def test_parse_receipt_image_returns_parsed_expense():
    with patch("backend.claude_parser._client") as mock_client:
        mock_client.messages.create.return_value = _mock_response(VALID_JSON)
        result = parse_receipt_image(b"fake-image-bytes", "image/jpeg")
    assert result is not None
    assert result.amount == 100.0
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `pytest tests/test_claude_parser.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create backend/claude_parser.py**

```python
import json
import base64
from datetime import date
from typing import Optional

import anthropic

from backend.config import settings
from backend.models import ParsedExpense

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_MODEL = "claude-haiku-4-5-20251001"

_CATEGORIES = [
    "Utilities", "Groceries", "Restaurants", "Transport",
    "Entertainment", "Health", "Shopping", "Travel", "Income", "Other",
]

_TEXT_SYSTEM = (
    "You extract expense details from natural-language messages. "
    "Respond ONLY with a valid JSON object — no explanation, no markdown."
)

_RECEIPT_SYSTEM = (
    "You read receipt images and extract expense details. "
    "Respond ONLY with a valid JSON object — no explanation, no markdown."
)

_JSON_SCHEMA = (
    '{"amount": <number>, "merchant": "<string>", "category": "<one of: {cats}>", '
    '"date": "<YYYY-MM-DD or null>", "notes": "<string or null>", "confidence": <0.0-1.0>}'
)


def parse_expense_text(text: str) -> Optional[ParsedExpense]:
    schema = _JSON_SCHEMA.format(cats=", ".join(_CATEGORIES))
    prompt = (
        f"Extract the expense from this message and return JSON matching: {schema}\n\n"
        f"Today is {date.today().isoformat()}. Use today for the date if not stated.\n\n"
        f"Message: {text}"
    )
    response = _client.messages.create(
        model=_MODEL,
        max_tokens=256,
        system=_TEXT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_response(response.content[0].text)


def parse_receipt_image(image_bytes: bytes, media_type: str) -> Optional[ParsedExpense]:
    schema = _JSON_SCHEMA.format(cats=", ".join(_CATEGORIES))
    b64 = base64.standard_b64encode(image_bytes).decode()
    response = _client.messages.create(
        model=_MODEL,
        max_tokens=256,
        system=_RECEIPT_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": f"Extract the expense and return JSON matching: {schema}"},
            ],
        }],
    )
    return _parse_response(response.content[0].text)


def _parse_response(text: str) -> Optional[ParsedExpense]:
    try:
        data = json.loads(text.strip())
        return ParsedExpense(**data)
    except Exception:
        return None
```

- [ ] **Step 4: Run tests — confirm they pass**

Run: `pytest tests/test_claude_parser.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/claude_parser.py tests/test_claude_parser.py
git commit -m "feat: Claude parser for receipt images and expense text"
```

---

## Task 8: Telegram bot

**Files:**
- Create: `backend/telegram_bot.py`
- Create: `register_webhook.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create backend/telegram_bot.py**

```python
import asyncio
import hmac
from datetime import date

from fastapi import APIRouter, Request, Header, HTTPException
from telegram import Bot

from backend.config import settings
from backend.claude_parser import parse_expense_text, parse_receipt_image
from backend.models import Transaction, TransactionCreate
from backend.sheets import SheetsClient

router = APIRouter(tags=["telegram"])
_bot = Bot(token=settings.telegram_bot_token)


def _verify_secret(token: str | None) -> bool:
    if token is None:
        return False
    return hmac.compare_digest(token, settings.telegram_webhook_secret)


async def _save_and_reply(chat_id: int, parsed, source_label: str) -> None:
    sheets = SheetsClient(spreadsheet_id=settings.google_sheets_id)
    expense_date = parsed.date or date.today()
    t = Transaction.from_create(
        TransactionCreate(
            date=expense_date,
            amount=parsed.amount,
            merchant=parsed.merchant,
            category=parsed.category,
            type="expense",
            notes=parsed.notes,
        ),
        source="telegram",
    )
    sheets.append_transaction(t)
    await _bot.send_message(
        chat_id=chat_id,
        text=f"Saved ({source_label}): ${t.amount:.2f} at {t.merchant} "
             f"[{t.category}] on {t.date}",
    )


async def _handle_text(chat_id: int, text: str) -> None:
    parsed = parse_expense_text(text)
    if not parsed or parsed.confidence < 0.5:
        await _bot.send_message(
            chat_id=chat_id,
            text="Couldn't parse that. Try: 'spent $X at [place] on [category]'",
        )
        return
    await _save_and_reply(chat_id, parsed, "text")


async def _handle_photo(chat_id: int, file_id: str) -> None:
    tg_file = await _bot.get_file(file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    parsed = parse_receipt_image(image_bytes, "image/jpeg")
    if not parsed or parsed.confidence < 0.5:
        await _bot.send_message(
            chat_id=chat_id,
            text="Couldn't read that receipt. Send the details as text instead.",
        )
        return
    await _save_and_reply(chat_id, parsed, "receipt")


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
):
    if not _verify_secret(x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()

    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id: int = message["chat"]["id"]

    if "text" in message:
        asyncio.create_task(_handle_text(chat_id, message["text"]))
    elif "photo" in message:
        largest = sorted(message["photo"], key=lambda p: p.get("file_size", 0))[-1]
        asyncio.create_task(_handle_photo(chat_id, largest["file_id"]))

    return {"ok": True}
```

- [ ] **Step 2: Register the Telegram router in backend/main.py**

Add at the bottom of the existing `app.include_router(...)` calls:

```python
from backend.telegram_bot import router as telegram_router
app.include_router(telegram_router)
```

- [ ] **Step 3: Create register_webhook.py**

```python
# register_webhook.py — run once after deploy (or with ngrok for local dev)
import asyncio
from telegram import Bot
from backend.config import settings

async def main():
    bot = Bot(token=settings.telegram_bot_token)
    url = f"{settings.app_url}/webhook"
    await bot.set_webhook(url=url, secret_token=settings.telegram_webhook_secret)
    info = await bot.get_webhook_info()
    print(f"Webhook set: {info.url}")

asyncio.run(main())
```

For local dev, install ngrok (`brew install ngrok`), run `ngrok http 8000`, update `APP_URL` in `.env` to the ngrok HTTPS URL, then:

Run: `python register_webhook.py`
Expected: `Webhook set: https://your-ngrok-url/webhook`

- [ ] **Step 4: Smoke-test the Telegram bot**

Send to your bot: `spent $12 at Starbucks on coffee`
Expected reply: `Saved (text): $12.00 at Starbucks [Restaurants] on 2026-04-20`
Verify: new row appears in your Google Sheet `Transactions` tab.

Send a photo of a receipt.
Expected reply: `Saved (receipt): $XX.XX at [merchant] [category] on [date]`

- [ ] **Step 5: Commit**

```bash
git add backend/telegram_bot.py backend/main.py register_webhook.py
git commit -m "feat: Telegram bot — receipt photo and natural language expense logging"
```

---

## Task 9: React frontend scaffold

**Files:**
- Create: `frontend/` (full Vite scaffold)
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/index.css`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create stub components in `frontend/src/components/`

- [ ] **Step 1: Scaffold the frontend**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install recharts react-router-dom
npm install -D @types/react @types/react-dom
```

- [ ] **Step 2: Create frontend/src/types.ts**

```typescript
export type TransactionType = "income" | "expense";
export type TransactionSource = "web" | "csv" | "telegram";

export interface Transaction {
  id: string;
  date: string;          // "YYYY-MM-DD"
  amount: number;
  merchant: string;
  category: string;
  type: TransactionType;
  source: TransactionSource;
  notes?: string;
}

export interface TransactionCreate {
  date: string;
  amount: number;
  merchant: string;
  category: string;
  type: TransactionType;
  notes?: string;
}

export interface Category {
  name: string;
  predefined: boolean;
}

export interface ImportPreviewRow {
  date: string;
  amount: number;
  merchant: string;
  category: string;
  type: string;
}

export interface ImportPreviewError {
  row: number;
  reason: string;
}
```

- [ ] **Step 3: Create frontend/src/api.ts**

```typescript
import type { Transaction, TransactionCreate, Category, ImportPreviewRow, ImportPreviewError } from "./types";

const BASE = "http://localhost:8000";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: options?.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : undefined,
    ...options,
  });
  if (res.status === 401) {
    window.location.href = `${BASE}/auth/login`;
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  getMe: () => req<{ email: string }>("/auth/me"),

  getTransactions: () => req<Transaction[]>("/api/transactions"),
  createTransaction: (data: TransactionCreate) =>
    req<Transaction>("/api/transactions", { method: "POST", body: JSON.stringify(data) }),
  deleteTransaction: (id: string) =>
    req<void>(`/api/transactions/${id}`, { method: "DELETE" }),

  getCategories: () => req<Category[]>("/api/categories"),
  createCategory: (name: string) =>
    req<Category>("/api/categories", { method: "POST", body: JSON.stringify({ name }) }),
  deleteCategory: (name: string) =>
    req<void>(`/api/categories/${encodeURIComponent(name)}`, { method: "DELETE" }),

  importPreview: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ valid_rows: ImportPreviewRow[]; errors: ImportPreviewError[] }>(
      "/api/import/preview", { method: "POST", body: form }
    );
  },
  importConfirm: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ imported: number }>("/api/import/confirm", { method: "POST", body: form });
  },
};
```

- [ ] **Step 4: Create frontend/src/index.css**

```css
*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 16px;
  background: #fafafa;
  color: #1a1a1a;
}

nav {
  background: #fff;
  border-bottom: 1px solid #e5e5e5;
  padding: 0.75rem 1rem;
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  align-items: center;
}

nav a { text-decoration: none; color: #555; font-weight: 500; }
nav a.active { color: #6c47ff; }

main { padding: 1rem; }

input, select, button, textarea {
  font-size: 16px; /* prevents iOS zoom */
}

table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem; text-align: left; }
thead tr { border-bottom: 2px solid #e5e5e5; }
tbody tr { border-bottom: 1px solid #f0f0f0; }

.card {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 1rem;
}

.summary-cards {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}

.summary-cards .card { flex: 1; min-width: 140px; }

button {
  cursor: pointer;
  padding: 0.5rem 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
}

button[type="submit"], button.primary {
  background: #6c47ff;
  color: #fff;
  border-color: #6c47ff;
}

input[type="text"], input[type="number"], input[type="date"],
input[type="month"], select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  margin-top: 0.25rem;
}

label { display: block; margin-bottom: 0.75rem; font-weight: 500; }

.amount-income { color: #16a34a; }
.amount-expense { color: #dc2626; }
```

- [ ] **Step 5: Create frontend/src/main.tsx**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 6: Create frontend/src/App.tsx**

```tsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import TransactionList from "./components/TransactionList";
import AddTransaction from "./components/AddTransaction";
import CsvImport from "./components/CsvImport";
import CategoryManager from "./components/CategoryManager";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/transactions">Transactions</NavLink>
        <NavLink to="/add">Add</NavLink>
        <NavLink to="/import">Import CSV</NavLink>
        <NavLink to="/categories">Categories</NavLink>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<TransactionList />} />
          <Route path="/add" element={<AddTransaction />} />
          <Route path="/import" element={<CsvImport />} />
          <Route path="/categories" element={<CategoryManager />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
```

- [ ] **Step 7: Create stub components**

Create each file below with exactly this content (replace later):

`frontend/src/components/Dashboard.tsx`:
```tsx
export default function Dashboard() { return <p>Dashboard loading…</p>; }
```

`frontend/src/components/TransactionList.tsx`:
```tsx
export default function TransactionList() { return <p>Transactions loading…</p>; }
```

`frontend/src/components/AddTransaction.tsx`:
```tsx
export default function AddTransaction() { return <p>Add transaction loading…</p>; }
```

`frontend/src/components/CsvImport.tsx`:
```tsx
export default function CsvImport() { return <p>CSV Import loading…</p>; }
```

`frontend/src/components/CategoryManager.tsx`:
```tsx
export default function CategoryManager() { return <p>Categories loading…</p>; }
```

- [ ] **Step 8: Confirm frontend starts**

Run: `cd frontend && npm run dev`
Expected: http://localhost:5173 opens with a nav bar and stub text on each route.

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat: React frontend scaffold with routing, typed API client, and global styles"
```

---

## Task 10: Dashboard component

**Files:**
- Modify: `frontend/src/components/Dashboard.tsx`

Shows: monthly income/expense/net summary cards + category bar chart + 6-month trend line chart.

- [ ] **Step 1: Replace Dashboard.tsx**

```tsx
import { useEffect, useState } from "react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "../api";
import type { Transaction } from "../types";

function monthKey(d: string) { return d.slice(0, 7); }
function currentMonth() { return new Date().toISOString().slice(0, 7); }
function lastNMonths(n: number): string[] {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date();
    d.setMonth(d.getMonth() - (n - 1 - i));
    return d.toISOString().slice(0, 7);
  });
}

export default function Dashboard() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);

  useEffect(() => { api.getTransactions().then(setTransactions); }, []);

  const month = currentMonth();
  const thisMonth = transactions.filter(t => t.date.startsWith(month));

  const totalIncome = thisMonth.filter(t => t.type === "income").reduce((s, t) => s + t.amount, 0);
  const totalExpenses = thisMonth.filter(t => t.type === "expense").reduce((s, t) => s + t.amount, 0);
  const net = totalIncome - totalExpenses;

  const byCategory: Record<string, number> = {};
  thisMonth.filter(t => t.type === "expense").forEach(t => {
    byCategory[t.category] = (byCategory[t.category] ?? 0) + t.amount;
  });
  const categoryData = Object.entries(byCategory)
    .map(([category, amount]) => ({ category, amount: +amount.toFixed(2) }))
    .sort((a, b) => b.amount - a.amount);

  const trendData = lastNMonths(6).map(m => ({
    month: m,
    expenses: +transactions.filter(t => t.date.startsWith(m) && t.type === "expense")
      .reduce((s, t) => s + t.amount, 0).toFixed(2),
    income: +transactions.filter(t => t.date.startsWith(m) && t.type === "income")
      .reduce((s, t) => s + t.amount, 0).toFixed(2),
  }));

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <h1>Dashboard — {month}</h1>

      <div className="summary-cards">
        <div className="card">
          <div style={{ color: "#555", fontSize: "0.85rem" }}>Income</div>
          <div className="amount-income" style={{ fontSize: "1.75rem", fontWeight: 700 }}>
            ${totalIncome.toFixed(2)}
          </div>
        </div>
        <div className="card">
          <div style={{ color: "#555", fontSize: "0.85rem" }}>Expenses</div>
          <div className="amount-expense" style={{ fontSize: "1.75rem", fontWeight: 700 }}>
            ${totalExpenses.toFixed(2)}
          </div>
        </div>
        <div className="card">
          <div style={{ color: "#555", fontSize: "0.85rem" }}>Net</div>
          <div
            className={net >= 0 ? "amount-income" : "amount-expense"}
            style={{ fontSize: "1.75rem", fontWeight: 700 }}
          >
            {net >= 0 ? "+" : ""}${net.toFixed(2)}
          </div>
        </div>
      </div>

      <h2>Spending by category (this month)</h2>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={categoryData} margin={{ left: 10 }}>
          <XAxis dataKey="category" tick={{ fontSize: 12 }} />
          <YAxis />
          <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
          <Bar dataKey="amount" fill="#6c47ff" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      <h2>6-month trend</h2>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={trendData} margin={{ left: 10 }}>
          <XAxis dataKey="month" tick={{ fontSize: 12 }} />
          <YAxis />
          <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
          <Legend />
          <Line type="monotone" dataKey="expenses" stroke="#dc2626" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="income" stroke="#16a34a" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Test in browser**

With backend running (`uvicorn backend.main:app --reload`) and frontend running (`npm run dev`), open http://localhost:5173.
Expected: Summary cards show $0 (empty data). Both charts render without errors.
Add a transaction via http://localhost:5173/add, then return to Dashboard.
Expected: The summary cards and category chart update to reflect the new entry.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Dashboard.tsx
git commit -m "feat: Dashboard with monthly summary cards and spending charts"
```

---

## Task 11: Transaction list

**Files:**
- Modify: `frontend/src/components/TransactionList.tsx`

- [ ] **Step 1: Replace TransactionList.tsx**

```tsx
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Transaction } from "../types";

export default function TransactionList() {
  const [all, setAll] = useState<Transaction[]>([]);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [type, setType] = useState<"all" | "income" | "expense">("all");
  const [category, setCategory] = useState("all");

  useEffect(() => { api.getTransactions().then(setAll); }, []);

  const categories = Array.from(new Set(all.map(t => t.category))).sort();
  const filtered = all.filter(t =>
    t.date.startsWith(month) &&
    (type === "all" || t.type === type) &&
    (category === "all" || t.category === category)
  );

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this transaction?")) return;
    await api.deleteTransaction(id);
    setAll(prev => prev.filter(t => t.id !== id));
  };

  return (
    <div style={{ maxWidth: 920, margin: "0 auto" }}>
      <h1>Transactions</h1>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <input type="month" value={month} onChange={e => setMonth(e.target.value)}
          style={{ width: "auto" }} />
        <select value={type} onChange={e => setType(e.target.value as typeof type)}
          style={{ width: "auto" }}>
          <option value="all">All types</option>
          <option value="income">Income</option>
          <option value="expense">Expense</option>
        </select>
        <select value={category} onChange={e => setCategory(e.target.value)}
          style={{ width: "auto" }}>
          <option value="all">All categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Date</th><th>Merchant</th><th>Category</th>
              <th style={{ textAlign: "right" }}>Amount</th>
              <th>Type</th><th>Source</th><th />
            </tr>
          </thead>
          <tbody>
            {filtered.map(t => (
              <tr key={t.id}>
                <td>{t.date}</td>
                <td>{t.merchant}</td>
                <td>{t.category}</td>
                <td style={{ textAlign: "right" }}
                  className={t.type === "expense" ? "amount-expense" : "amount-income"}>
                  {t.type === "expense" ? "-" : "+"}${t.amount.toFixed(2)}
                </td>
                <td>{t.type}</td>
                <td>{t.source}</td>
                <td>
                  <button onClick={() => handleDelete(t.id)}
                    style={{ color: "#dc2626", border: "none", background: "none", padding: "0.25rem" }}>
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length === 0 && <p style={{ color: "#888" }}>No transactions for this filter.</p>}
    </div>
  );
}
```

- [ ] **Step 2: Test in browser**

Open http://localhost:5173/transactions.
Change the month filter — list updates.
Change type/category — list filters correctly.
Delete a transaction — row disappears without page reload.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TransactionList.tsx
git commit -m "feat: transaction list with month, type, and category filters"
```

---

## Task 12: Add transaction form

**Files:**
- Modify: `frontend/src/components/AddTransaction.tsx`

- [ ] **Step 1: Replace AddTransaction.tsx**

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Category } from "../types";

export default function AddTransaction() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    amount: "",
    merchant: "",
    category: "",
    type: "expense" as "income" | "expense",
    notes: "",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.getCategories().then(setCategories); }, []);

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.amount || !form.merchant || !form.category) {
      setError("Amount, merchant, and category are required.");
      return;
    }
    setSaving(true);
    try {
      await api.createTransaction({
        date: form.date,
        amount: parseFloat(form.amount),
        merchant: form.merchant,
        category: form.category,
        type: form.type,
        notes: form.notes || undefined,
      });
      navigate("/transactions");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg.includes("409") ? "Duplicate transaction detected." : "Failed to save.");
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: 480, margin: "0 auto" }}>
      <h1>Add Transaction</h1>
      {error && <p style={{ color: "#dc2626" }}>{error}</p>}
      <form onSubmit={handleSubmit}>
        <label>Date <input type="date" value={form.date} onChange={set("date")} /></label>
        <label>Amount ($) <input type="number" step="0.01" min="0.01" value={form.amount} onChange={set("amount")} placeholder="0.00" /></label>
        <label>Merchant <input type="text" value={form.merchant} onChange={set("merchant")} placeholder="e.g. Trader Joe's" /></label>
        <label>
          Category
          <select value={form.category} onChange={set("category")}>
            <option value="">Select category</option>
            {categories.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label>
          Type
          <select value={form.type} onChange={set("type")}>
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </select>
        </label>
        <label>Notes (optional) <input type="text" value={form.notes} onChange={set("notes")} /></label>
        <button type="submit" className="primary" disabled={saving} style={{ marginTop: "0.5rem", width: "100%" }}>
          {saving ? "Saving…" : "Save Transaction"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Test in browser**

Open http://localhost:5173/add.
Fill form and submit — redirects to /transactions, new entry visible.
Try submitting the same transaction again — duplicate error message appears.
Try submitting with empty merchant — validation error appears.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AddTransaction.tsx
git commit -m "feat: add transaction form with duplicate detection feedback"
```

---

## Task 13: CSV import UI

**Files:**
- Modify: `frontend/src/components/CsvImport.tsx`

- [ ] **Step 1: Replace CsvImport.tsx**

```tsx
import { useState } from "react";
import { api } from "../api";
import type { ImportPreviewRow, ImportPreviewError } from "../types";

export default function CsvImport() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{
    valid_rows: ImportPreviewRow[];
    errors: ImportPreviewError[];
  } | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePreview = async () => {
    if (!file) return;
    setError(null);
    setResult(null);
    try {
      setPreview(await api.importPreview(file));
    } catch {
      setError("Failed to parse CSV. Check that all required columns are present.");
    }
  };

  const handleConfirm = async () => {
    if (!file || !preview) return;
    setImporting(true);
    try {
      const data = await api.importConfirm(file);
      setResult(`Imported ${data.imported} transactions successfully.`);
      setPreview(null);
      setFile(null);
    } catch {
      setError("Import failed. Please try again.");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <h1>Import CSV</h1>
      <p>Required columns: <code>date</code>, <code>amount</code>, <code>merchant</code>, <code>category</code>, <code>type</code></p>
      <p style={{ fontSize: "0.875rem", color: "#555" }}>Date format: YYYY-MM-DD. Type: <code>income</code> or <code>expense</code>.</p>

      {error && <p style={{ color: "#dc2626" }}>{error}</p>}
      {result && <p style={{ color: "#16a34a" }}>{result}</p>}

      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "1rem" }}>
        <input type="file" accept=".csv"
          onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null); setResult(null); }} />
        <button onClick={handlePreview} disabled={!file}>Preview</button>
      </div>

      {preview && (
        <>
          {preview.errors.length > 0 && (
            <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 6, padding: "0.75rem", marginBottom: "1rem" }}>
              <strong>Rows with errors (will be skipped):</strong>
              {preview.errors.map(e => (
                <div key={e.row} style={{ fontSize: "0.875rem" }}>Row {e.row}: {e.reason}</div>
              ))}
            </div>
          )}

          <h3>{preview.valid_rows.length} valid rows</h3>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th><th>Merchant</th><th>Category</th>
                  <th style={{ textAlign: "right" }}>Amount</th><th>Type</th>
                </tr>
              </thead>
              <tbody>
                {preview.valid_rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.date}</td>
                    <td>{r.merchant}</td>
                    <td>{r.category}</td>
                    <td style={{ textAlign: "right" }}>${r.amount.toFixed(2)}</td>
                    <td>{r.type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button
            className="primary"
            onClick={handleConfirm}
            disabled={importing || preview.valid_rows.length === 0}
            style={{ marginTop: "1rem" }}
          >
            {importing ? "Importing…" : `Import ${preview.valid_rows.length} transactions`}
          </button>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create a test CSV file**

```csv
date,amount,merchant,category,type
2026-04-01,47.50,Trader Joe's,Groceries,expense
2026-04-02,3000.00,Employer,Income,income
2026-04-03,bad-amount,Test Store,Other,expense
```

- [ ] **Step 3: Test in browser**

Upload the test CSV → click Preview.
Expected: 2 valid rows shown, 1 error listed ("Row 3: could not convert string to float").
Click "Import 2 transactions".
Expected: "Imported 2 transactions successfully." Open Google Sheet to verify the 2 rows appear.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CsvImport.tsx
git commit -m "feat: CSV import UI with row preview, error display, and confirm step"
```

---

## Task 14: Category manager

**Files:**
- Modify: `frontend/src/components/CategoryManager.tsx`

- [ ] **Step 1: Replace CategoryManager.tsx**

```tsx
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Category } from "../types";

export default function CategoryManager() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { api.getCategories().then(setCategories); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setError("");
    try {
      const cat = await api.createCategory(newName.trim());
      setCategories(prev => [...prev, cat]);
      setNewName("");
    } catch {
      setError("Failed to add category.");
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete "${name}"?`)) return;
    await api.deleteCategory(name);
    setCategories(prev => prev.filter(c => c.name !== name));
  };

  const predefined = categories.filter(c => c.predefined);
  const custom = categories.filter(c => !c.predefined);

  return (
    <div style={{ maxWidth: 480, margin: "0 auto" }}>
      <h1>Categories</h1>
      {error && <p style={{ color: "#dc2626" }}>{error}</p>}

      <h2>Predefined</h2>
      <ul style={{ paddingLeft: "1.25rem" }}>
        {predefined.map(c => <li key={c.name}>{c.name}</li>)}
      </ul>

      <h2>Custom</h2>
      {custom.length === 0 && <p style={{ color: "#888" }}>No custom categories yet.</p>}
      <ul style={{ paddingLeft: "1.25rem" }}>
        {custom.map(c => (
          <li key={c.name} style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.25rem" }}>
            {c.name}
            <button onClick={() => handleDelete(c.name)}
              style={{ color: "#dc2626", border: "none", background: "none", padding: "0 0.25rem" }}>×</button>
          </li>
        ))}
      </ul>

      <form onSubmit={handleAdd} style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
        <input
          type="text"
          placeholder="New category name"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          style={{ flex: 1 }}
        />
        <button type="submit" className="primary">Add</button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Test in browser**

Open http://localhost:5173/categories.
Expected: 10 predefined categories listed. Custom section shows "No custom categories yet."
Add a custom category — it appears in the Custom list.
Delete it — it disappears.
Verify the new category appears in the Add Transaction form's dropdown.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CategoryManager.tsx
git commit -m "feat: category manager — view predefined, add and delete custom categories"
```

---

## Task 15: Mobile layout verification

**Files:**
- No new files — verify existing CSS handles mobile correctly.

- [ ] **Step 1: Open Chrome DevTools mobile emulation**

In Chrome, press `Cmd+Shift+M` (Mac) or `Ctrl+Shift+M` (Windows/Linux) to toggle device toolbar. Select **iPhone 12 Pro** (390×844).

- [ ] **Step 2: Test each screen**

Visit each route and verify:

| Route | Check |
|---|---|
| `/` | Summary cards stack vertically. Charts are full-width. No horizontal scroll. |
| `/transactions` | Table scrolls horizontally inside its container. Filters wrap to new lines. |
| `/add` | Form fields are full width. Submit button is full width. No zoom on input focus. |
| `/import` | Preview table scrolls horizontally. Buttons are tappable. |
| `/categories` | Add form fits in one row or wraps gracefully. |

- [ ] **Step 3: Fix any overflow issues found**

If any screen causes horizontal page overflow, add `overflow-x: hidden` to the relevant container in `index.css` or the component's inline style.

- [ ] **Step 4: Commit if any fixes were made**

```bash
git add frontend/src/index.css frontend/src/components/
git commit -m "fix: mobile layout overflow corrections"
```

---

## Self-Review

**Spec coverage:**
- ✅ Google OAuth (email whitelist) — Task 5
- ✅ Google Sheets backend — Tasks 3, 4
- ✅ CSV import — Tasks 6, 13
- ✅ Track income vs expenses — Tasks 4, 10
- ✅ Spending by category — Task 10
- ✅ Predefined + custom categories — Tasks 3, 4, 14
- ✅ Monthly summary dashboard — Task 10
- ✅ 6-month trend charts — Task 10
- ✅ Add expenses from web — Task 12
- ✅ Telegram: natural language text — Tasks 7, 8
- ✅ Telegram: receipt photos via Claude — Tasks 7, 8
- ✅ Duplicate detection with warning — Tasks 3, 4, 12
- ✅ Mobile-responsive layout — Tasks 9, 15
- ✅ Error handling: CSV bad rows — Tasks 6, 13
- ✅ Error handling: Telegram parse failure — Task 8

**Placeholder scan:** No TBDs, no "handle edge cases" without code, no forward references to undefined types.

**Type consistency:** `Transaction.from_create` defined in Task 2, called in Tasks 4, 8. `SheetsClient` defined in Task 3, used in Tasks 4, 6, 8. `parse_expense_text`/`parse_receipt_image` defined in Task 7, called in Task 8. `ImportPreviewRow`/`ImportPreviewError` defined in Task 9 (`types.ts`), used in Task 13.
