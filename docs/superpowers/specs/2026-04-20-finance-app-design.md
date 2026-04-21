# Personal Finance App — Design Spec

**Date:** 2026-04-20

## Goal

A personal cash flow tracker with full visibility into income vs. expenses, spending by category, and trends over time. Accessible via a mobile-responsive web app and a Telegram bot.

---

## Architecture

Single FastAPI backend serving both the web app and the Telegram webhook. No separate services. Google Sheets is the sole data store.

```
┌─────────────────────────────────────────┐
│              FastAPI Backend             │
│                                         │
│  /auth     → Google OAuth 2.0           │
│  /api/*    → REST endpoints             │
│  /webhook  → Telegram bot               │
└────────┬──────────────┬─────────────────┘
         │              │
    React SPA      Telegram Bot
   (dashboard)    (receipts + text)
         │              │
         └──────┬───────┘
                │
        Google Sheets API
        (single spreadsheet
         with multiple tabs)
```

**Google Sheets structure:**
- `Transactions` tab — every income/expense entry: date, amount, merchant, category, type (income/expense), source (web/csv/telegram)
- `Categories` tab — predefined + custom categories
- Monthly summaries are computed by the backend on read (not stored)

**External services:**
- Google Sheets API — persistence (service account credentials)
- Google OAuth 2.0 — authentication
- Telegram Bot API — receipt photos and natural language expense input
- Claude API (claude-sonnet-4-6) — receipt OCR and natural language parsing

---

## Components

### Web App (React, mobile-responsive)

| Screen | Description |
|---|---|
| Login | "Sign in with Google" button |
| Dashboard | Monthly income vs. expenses summary + trend charts by category |
| Transactions list | Filterable by month, category, type |
| Add transaction | Form: date, amount, merchant, category, income/expense toggle |
| CSV import | Upload → preview parsed rows → confirm to save |
| Category management | View, add, delete custom categories |

The frontend is fully responsive and works well on mobile browsers. No PWA required.

### Telegram Bot

**Receipt photo flow:**
1. User sends a photo of a receipt
2. Claude Vision extracts merchant, date, amount, suggests a category
3. Bot replies with the parsed data and asks for confirmation or correction
4. On confirmation, saves to Sheets

**Natural language flow:**
1. User sends text like "spent $100 at Trader Joe's on groceries today"
2. Claude parses merchant, amount, date, category
3. Bot confirms parsed data
4. On confirmation, saves to Sheets

---

## Authentication & Security

- Google OAuth 2.0 login
- Only the owner's Google account is whitelisted (by email)
- Sessions stored server-side with a secure cookie
- All routes and API endpoints require an active session; unauthenticated requests redirect to login

---

## Error Handling

| Scenario | Behavior |
|---|---|
| CSV invalid rows | Flagged in preview; user chooses to skip or fix before saving |
| Claude can't parse receipt confidently | Bot asks for clarification before saving |
| Ambiguous Telegram text | Bot asks a follow-up question |
| Google Sheets API failure | Clear error returned; nothing silently lost |
| Duplicate transaction | Warning shown if same date + amount + merchant already exists |

---

## Categories

**Predefined:**
Utilities, Groceries, Restaurants, Transport, Entertainment, Health, Shopping, Travel, Income, Other

**Custom:**
User can add and delete their own categories via the web app. Custom categories live in the `Categories` tab in Sheets.

---

## Testing

- **Backend unit tests** — CSV parsing, transaction validation, Claude response parser (receipts + text)
- **Integration tests** — Google Sheets write/read cycle using a dedicated test spreadsheet
- **Telegram bot tests** — Claude parsing logic tested in isolation with fixture receipts and text samples (no live Telegram connection needed)
- **Frontend component tests** — add-transaction form, CSV import preview
- **Mobile layout** — manual testing on mobile browser
- **Auth** — verify non-whitelisted Google accounts are rejected

---

## Out of Scope

- Push notifications
- Multi-user support
- Bank API integrations (Plaid, etc.)
- PWA / installable app
- Budgeting / savings goals
