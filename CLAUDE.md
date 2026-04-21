# cleo-finance

Personal cash flow tracker — FastAPI backend, React frontend, Google Sheets as data store.

---

## Project History

### 2026-04-20 — Session 1: Design & planning

Brainstormed the app architecture and wrote two docs:

- `docs/superpowers/specs/2026-04-20-finance-app-design.md` — full design spec covering architecture, components, authentication, error handling, and out-of-scope items
- `docs/superpowers/plans/2026-04-20-finance-app.md` — 15-task TDD implementation plan with exact file contents for every step

**Tech stack decided:** Python 3.11+, FastAPI, Google Sheets API (service account), Google OAuth 2.0, Claude Haiku (receipt/text parsing), python-telegram-bot, React 18 + TypeScript + Vite, Recharts.

---

### 2026-04-20 — Session 2: Backend implementation

Executed the plan task by task, working directly on `main`. All backend code lives in `finances/`.

**Task 1 — Project scaffold** (`2ba74f4`)
Created `requirements.txt`, `.env.example`, `.gitignore`, `backend/config.py` (pydantic-settings with `get_settings()` lazy factory), `backend/main.py` (FastAPI + CORS), `tests/conftest.py`, `pyproject.toml` (pytest asyncio_mode=auto). Settings use `@lru_cache` and `frontend_url` is configurable rather than hardcoded.

**Task 2 — Pydantic models** (`2ba74f4`)
Created `backend/models.py`: `TransactionCreate`, `Transaction` (with `from_create` classmethod), `Category` (name auto-stripped), `ParsedExpense`. Validators enforce positive amounts. 5 tests in `tests/test_models.py`.

**Task 3 — Google Sheets client** (`5d16e66`)
Created `backend/sheets.py` (`SheetsClient` class) with full CRUD: `append_transaction`, `get_all_transactions`, `delete_transaction`, `find_duplicate`, `get_categories`, `append_category`, `delete_category`. Created `backend/init_sheets.py` (one-shot script to set headers and predefined categories). 3 mock-based tests in `tests/test_sheets.py`.

**Task 4 — Transactions and Categories API** (`cad2a0b`)
Created `backend/transactions.py` (`/api/transactions` router — list, create with duplicate detection, delete), `backend/categories.py` (`/api/categories` router — list, create, delete), stub `backend/auth.py` (session reading + `require_auth` dependency). Updated `main.py` to register all routers with auth dependency. 5 tests in `tests/test_transactions.py`.

**Task 5 — Google OAuth** (`af82421`)
Expanded `backend/auth.py` with full OAuth2 flow: `GET /auth/login` (redirects to Google), `GET /auth/callback` (verifies token, checks email whitelist, sets signed cookie), `GET /auth/logout`, `GET /auth/me`. Uses `itsdangerous` for session signing. `OAUTHLIB_INSECURE_TRANSPORT=1` set for local HTTP dev.

**Task 6 — CSV import** (`62ef3df`)
Created `backend/csv_import.py`: `parse_csv()` returns `(valid_rows, errors)`, `CsvParseError` for missing columns, `CsvRowError` for bad rows. Added `POST /api/import/preview` and `POST /api/import/confirm` endpoints to `main.py`. 3 tests in `tests/test_csv_import.py`.

**Task 7 — Claude parser** (`8513d0a`)
Created `backend/claude_parser.py`: `parse_expense_text(text)` and `parse_receipt_image(bytes, media_type)` using `claude-haiku-4-5-20251001`. Both return `Optional[ParsedExpense]` and gracefully return `None` on malformed JSON. Note: `ParsedExpense.date` field uses `from datetime import date as date_type` to avoid shadowing in Python 3.9. 3 mock-based tests in `tests/test_claude_parser.py`.

**Task 8 — Telegram bot** (`d6842bf`)
Created `backend/telegram_bot.py`: `POST /webhook` endpoint with HMAC secret verification, fire-and-forget `asyncio.create_task` for text and photo handlers. Text → Claude NL parsing. Photo → Claude vision parsing. Both save to Sheets and reply with confirmation. Created `register_webhook.py` (run once to register with Telegram). Bot instantiation is deferred (`_get_bot()`) to avoid import-time failures with placeholder credentials.

**Final backend test count: 19 passing.**

---

### 2026-04-21 — Session 3: Frontend implementation

**Task 9 — React scaffold** (`8b94cef`)
Vite + React + TypeScript scaffold at `finances/frontend/`. Created `src/types.ts` (shared interfaces), `src/api.ts` (typed fetch client with 401 → redirect to `/auth/login`), `src/index.css` (mobile-first global styles), `src/App.tsx` (BrowserRouter + NavLink layout, 5 routes). Stub components created for all 5 views.

**Tasks 10–14 — Frontend components** (`0b51097`)

- `Dashboard.tsx` — Monthly income/expense/net summary cards + category bar chart + 6-month trend line chart (Recharts)
- `TransactionList.tsx` — Filterable table by month, type, and category; inline delete with optimistic update
- `AddTransaction.tsx` — Form with date, amount, merchant, category, type, notes; navigates to `/transactions` on success; shows duplicate detection error (409)
- `CsvImport.tsx` — File upload → preview (valid rows + error rows) → confirm import
- `CategoryManager.tsx` — Predefined categories (read-only list) + custom categories (add/delete)

TypeScript compilation: zero errors.

---

## Prerequisites (manual setup required before running)

1. **Google Cloud project** — Enable Sheets API and OpenID/Google+ API
2. **Service account** — Download JSON key → save as `finances/backend/service-account.json`
3. **Google Spreadsheet** — Create one, share with service account (Editor), add tabs named exactly `Transactions` and `Categories`
4. **OAuth2 credentials** — Web application type, add `http://localhost:8000/auth/callback` as redirect URI
5. **Telegram bot** — Message @BotFather → `/newbot`, note the token
6. **Anthropic API key** — From console.anthropic.com

## Running locally

```bash
# Backend
cd finances
cp .env.example .env        # fill in real values
python3 -m backend.init_sheets   # one-time: sets up sheet headers + predefined categories
uvicorn backend.main:app --reload

# Frontend (separate terminal)
cd finances/frontend
npm run dev

# Register Telegram webhook (after ngrok or deploy)
# Update APP_URL in .env to your public HTTPS URL first
cd finances
python3 register_webhook.py
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
