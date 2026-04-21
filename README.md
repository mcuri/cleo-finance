# cleo-finance

A personal cash flow tracker with a web dashboard and a Telegram bot for logging expenses on the go.

## Features

- **Dashboard** — Monthly income vs. expenses summary, spending by category (bar chart), 6-month trend (line chart)
- **Transaction management** — Add, filter, and delete transactions; duplicate detection
- **CSV import** — Upload a CSV, preview parsed rows, confirm to save
- **Category management** — Predefined categories + add your own custom ones
- **Telegram bot** — Send a text message or a photo of a receipt; Claude parses it and saves it automatically
- **Google OAuth** — Single-user, email-whitelisted login via Google

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, uvicorn |
| Data store | Google Sheets (service account) |
| Auth | Google OAuth 2.0 + signed session cookie |
| AI parsing | Claude Haiku (`claude-haiku-4-5-20251001`) |
| Telegram | python-telegram-bot 21+ |
| Frontend | React 18, TypeScript, Vite, Recharts |

## Project structure

```
finances/
├── backend/
│   ├── main.py              # FastAPI app, router registration, CORS
│   ├── config.py            # Settings from .env (pydantic-settings)
│   ├── auth.py              # Google OAuth2 + signed-cookie session
│   ├── models.py            # Pydantic models
│   ├── sheets.py            # Google Sheets CRUD (service account)
│   ├── transactions.py      # /api/transactions router
│   ├── categories.py        # /api/categories router
│   ├── csv_import.py        # CSV parsing logic
│   ├── claude_parser.py     # Claude: receipt OCR + NL text parsing
│   ├── telegram_bot.py      # /webhook Telegram handler
│   └── init_sheets.py       # One-time setup script
├── tests/                   # 19 pytest tests (all mocked, no real API calls)
├── frontend/
│   └── src/
│       ├── api.ts            # Typed fetch client
│       ├── types.ts          # Shared TypeScript interfaces
│       └── components/       # Dashboard, TransactionList, AddTransaction, CsvImport, CategoryManager
├── register_webhook.py      # One-time Telegram webhook registration
├── .env.example
└── requirements.txt
```

## Setup

### 1. Google Cloud

1. Create a project and enable the **Google Sheets API** and **Google+ / OpenID API**
2. Create a **service account**, download the JSON key → save as `finances/backend/service-account.json`
3. Create a **Google Spreadsheet**, share it with the service account email (Editor role), and add two tabs named exactly `Transactions` and `Categories`
4. Create **OAuth2 Web Application credentials**, add `http://localhost:8000/auth/callback` as an authorised redirect URI

### 2. Telegram & Anthropic

- Message [@BotFather](https://t.me/BotFather) → `/newbot` → note the token
- Get an API key from [console.anthropic.com](https://console.anthropic.com)

### 3. Environment

```bash
cd finances
cp .env.example .env
# Fill in all values in .env
```

### 4. Install dependencies

```bash
pip install -r finances/requirements.txt
cd finances/frontend && npm install
```

### 5. Initialise the spreadsheet (once)

```bash
cd finances
python3 -m backend.init_sheets
```

This writes the column headers and 10 predefined categories to your spreadsheet.

## Running locally

```bash
# Terminal 1 — backend
cd finances
uvicorn backend.main:app --reload

# Terminal 2 — frontend
cd finances/frontend
npm run dev
```

- App: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Sign in at http://localhost:8000/auth/login — only the email set in `ALLOWED_EMAIL` can access the app.

## Telegram bot (local dev)

Use [ngrok](https://ngrok.com) to expose the local backend:

```bash
ngrok http 8000
# Update APP_URL in .env to the ngrok HTTPS URL
python3 finances/register_webhook.py
```

Send your bot a message like `spent $12 at Starbucks on coffee` or a photo of a receipt.

## Tests

```bash
cd finances
python3 -m pytest tests/ -v
```

19 tests, all using mocks — no real Google or Anthropic credentials needed.
