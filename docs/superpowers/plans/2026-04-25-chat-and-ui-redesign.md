# Chat View & UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dark minimal UI theme and a full-page Chat view where the user can paste bulk expenses and ask freeform questions about their finances.

**Architecture:** The chat endpoint (`POST /api/chat`) parses any embedded expenses from the message, saves non-duplicates to Sheets, then fetches all transactions and passes them as context to Claude Haiku to answer the user's question. The frontend stores conversation history in `localStorage` and renders a bubble-style chat UI.

**Tech Stack:** FastAPI, Anthropic SDK (claude-haiku-4-5-20251001), Google Sheets API, React 18 + TypeScript + Vite, React Router.

---

## File Map

**Create:**
- `finances/backend/anthropic_logger.py` — shared `log_usage()` helper (stdout + Sheets)
- `finances/backend/chat.py` — `POST /api/chat` endpoint
- `finances/frontend/src/components/Chat.tsx` — chat UI component
- `finances/tests/test_chat.py` — tests for chat endpoint

**Modify:**
- `finances/backend/sheets.py` — add `append_log()` method
- `finances/backend/init_sheets.py` — add Logs tab initialization
- `finances/backend/claude_parser.py` — call `log_usage()` after each API call
- `finances/backend/main.py` — register chat router + logging config
- `finances/frontend/src/types.ts` — add `ChatMessage` interface
- `finances/frontend/src/api.ts` — add `chat()` method
- `finances/frontend/src/index.css` — dark theme CSS variables
- `finances/frontend/src/App.tsx` — add Chat route + nav
- `finances/frontend/src/components/Dashboard.tsx` — use CSS variables
- `finances/frontend/src/components/TransactionList.tsx` — use CSS variables
- `finances/frontend/src/components/AddTransaction.tsx` — use CSS variables
- `finances/frontend/src/components/CsvImport.tsx` — use CSS variables
- `finances/frontend/src/components/CategoryManager.tsx` — use CSS variables

---

## Task 1: Google Sheets Logs Tab

**Files:**
- Modify: `finances/backend/sheets.py`
- Modify: `finances/backend/init_sheets.py`
- Modify: `finances/tests/test_sheets.py`

- [ ] **Step 1: Write the failing test**

Add to `finances/tests/test_sheets.py`:

```python
def test_append_log(sheets_client, mock_service):
    sheets_client.append_log("chat", "claude-haiku-4-5-20251001", 100, 50)
    kwargs = mock_service.spreadsheets().values().append.call_args[1]
    assert kwargs["range"] == "Logs!A:E"
    row = kwargs["body"]["values"][0]
    assert row[1] == "chat"
    assert row[2] == "claude-haiku-4-5-20251001"
    assert row[3] == 100
    assert row[4] == 50
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd finances
pytest tests/test_sheets.py::test_append_log -v
```

Expected: `FAILED` — `AttributeError: 'SheetsClient' object has no attribute 'append_log'`

- [ ] **Step 3: Add `append_log` to `SheetsClient`**

In `finances/backend/sheets.py`, add after `delete_category`:

```python
def append_log(self, endpoint: str, model: str, input_tokens: int, output_tokens: int) -> None:
    from datetime import datetime
    row = [datetime.utcnow().isoformat(), endpoint, model, input_tokens, output_tokens]
    self._values().append(
        spreadsheetId=self.spreadsheet_id,
        range="Logs!A:E",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_sheets.py::test_append_log -v
```

Expected: `PASSED`

- [ ] **Step 5: Add Logs tab initialization to `init_sheets.py`**

In `finances/backend/init_sheets.py`, inside `init()` after the Categories block:

```python
vals.update(
    spreadsheetId=settings.google_sheets_id,
    range="Logs!A1:E1",
    valueInputOption="RAW",
    body={"values": [["timestamp", "endpoint", "model", "input_tokens", "output_tokens"]]},
).execute()
```

Also add `"Logs"` to the print message: `print("Sheets initialised (Transactions, Categories, Logs).")`

- [ ] **Step 6: Run init script to create the Logs tab**

```bash
cd finances
python3 -m backend.init_sheets
```

Expected: `Sheets initialised (Transactions, Categories, Logs).`

Verify a `Logs` tab now exists in your Google Spreadsheet with 5 header columns.

- [ ] **Step 7: Commit**

```bash
git add finances/backend/sheets.py finances/backend/init_sheets.py finances/tests/test_sheets.py
git commit -m "feat: add Logs tab to Google Sheets with append_log method"
```

---

## Task 2: Anthropic Logging Helper

**Files:**
- Create: `finances/backend/anthropic_logger.py`
- Modify: `finances/backend/claude_parser.py`
- Modify: `finances/backend/main.py`

- [ ] **Step 1: Create `anthropic_logger.py`**

Create `finances/backend/anthropic_logger.py`:

```python
import logging

logger = logging.getLogger("anthropic")


def log_usage(response, endpoint: str) -> None:
    model = response.model
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    logger.info(
        "model=%s input_tokens=%d output_tokens=%d endpoint=%s",
        model, input_tokens, output_tokens, endpoint,
    )

    try:
        from backend.sheets import SheetsClient
        from backend.config import get_settings
        sheets = SheetsClient(spreadsheet_id=get_settings().google_sheets_id)
        sheets.append_log(endpoint, model, input_tokens, output_tokens)
    except Exception as exc:
        logger.warning("Failed to log to Sheets: %s", exc)
```

- [ ] **Step 2: Enable logging in `main.py`**

At the top of `finances/backend/main.py`, after the existing imports, add:

```python
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
```

- [ ] **Step 3: Call `log_usage` in `claude_parser.py`**

In `finances/backend/claude_parser.py`, add the import after existing imports:

```python
from backend.anthropic_logger import log_usage
```

In `parse_expense_text`, after `response = _client.messages.create(...)` and before `return _parse_response(...)`:

```python
    log_usage(response, "parse_expense_text")
```

In `parse_receipt_image`, after `response = _client.messages.create(...)` and before `return _parse_response(...)`:

```python
    log_usage(response, "parse_receipt_image")
```

- [ ] **Step 4: Verify logging works locally**

```bash
cd finances
uvicorn backend.main:app --reload
```

In another terminal, trigger a parse call (you can send a message via the Telegram bot or use the existing tests). Check the uvicorn terminal — you should see lines like:

```
INFO anthropic model=claude-haiku-4-5-20251001 input_tokens=234 output_tokens=87 endpoint=parse_expense_text
```

- [ ] **Step 5: Run all existing tests to confirm nothing broke**

```bash
cd finances
pytest -v
```

Expected: all 19 tests pass.

- [ ] **Step 6: Commit**

```bash
git add finances/backend/anthropic_logger.py finances/backend/claude_parser.py finances/backend/main.py
git commit -m "feat: log Anthropic API usage to stdout and Google Sheets"
```

---

## Task 3: Backend Chat Endpoint

**Files:**
- Create: `finances/backend/chat.py`
- Create: `finances/tests/test_chat.py`
- Modify: `finances/backend/main.py`

- [ ] **Step 1: Write the failing tests**

Create `finances/tests/test_chat.py`:

```python
from unittest.mock import MagicMock, patch
from datetime import date
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def mock_sheets():
    m = MagicMock()
    m.get_all_transactions.return_value = []
    m.find_duplicate.return_value = False
    return m


@pytest.fixture
def client(mock_sheets):
    with patch("backend.chat.get_sheets_client", return_value=mock_sheets), \
         patch("backend.auth.require_auth", return_value={"email": "test@test.com"}):
        yield TestClient(app)


def test_chat_returns_reply(client, mock_sheets):
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="You have no transactions yet.")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=20)
        mock_response.model = "claude-haiku-4-5-20251001"
        mock_cls.return_value.messages.create.return_value = mock_response

        resp = client.post("/api/chat", json={"message": "hello", "history": []})

    assert resp.status_code == 200
    assert resp.json()["reply"] == "You have no transactions yet."


def test_chat_saves_parsed_expense(client, mock_sheets):
    from backend.models import ParsedExpense
    parsed = ParsedExpense(
        amount=15.66, merchant="The Brazilian Spot",
        category="Restaurants", date=date(2026, 4, 18), confidence=0.9,
    )
    with patch("backend.chat.parse_expense_text", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Saved 1 expense.")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=10)
        mock_response.model = "claude-haiku-4-5-20251001"
        mock_cls.return_value.messages.create.return_value = mock_response

        resp = client.post("/api/chat", json={
            "message": "Stanford FCU charge $15.66 at The Brazilian Spot",
            "history": [],
        })

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_called_once()


def test_chat_skips_duplicate(client, mock_sheets):
    from backend.models import ParsedExpense
    mock_sheets.find_duplicate.return_value = True
    parsed = ParsedExpense(
        amount=15.66, merchant="The Brazilian Spot",
        category="Restaurants", date=date(2026, 4, 18), confidence=0.9,
    )
    with patch("backend.chat.parse_expense_text", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Skipped duplicate.")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=10)
        mock_response.model = "claude-haiku-4-5-20251001"
        mock_cls.return_value.messages.create.return_value = mock_response

        resp = client.post("/api/chat", json={
            "message": "Stanford FCU charge $15.66 at The Brazilian Spot",
            "history": [],
        })

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd finances
pytest tests/test_chat.py -v
```

Expected: `ERROR` — cannot import `backend.chat`

- [ ] **Step 3: Create `finances/backend/chat.py`**

```python
import json
import logging
from datetime import date as date_type
from typing import List

import anthropic
import backend.chat as _self
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.anthropic_logger import log_usage
from backend.auth import require_auth
from backend.claude_parser import parse_expense_text
from backend.config import get_settings
from backend.models import Transaction, TransactionCreate
from backend.sheets import SheetsClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

_MODEL = "claude-haiku-4-5-20251001"
_SYSTEM = (
    "You are Cleo, a personal finance assistant. "
    "You have access to the user's complete transaction history provided below. "
    "Answer questions concisely and specifically using the data. "
    "If expenses were just saved, acknowledge them first before answering any question. "
    "Use dollar amounts and dates from the data. Be brief — 2-4 sentences max unless detail is needed."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=get_settings().google_sheets_id)


def _get_sheets_client():
    return _self.get_sheets_client()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request_body: ChatRequest,
    sheets: SheetsClient = Depends(_get_sheets_client),
    session: dict = Depends(require_auth),
):
    # 1. Parse and save any expenses embedded in the message
    saved: List[Transaction] = []
    skipped_count = 0
    for parsed in parse_expense_text(request_body.message):
        expense_date = parsed.date or date_type.today()
        if sheets.find_duplicate(expense_date, parsed.amount, parsed.merchant):
            skipped_count += 1
        else:
            t = Transaction.from_create(
                TransactionCreate(
                    date=expense_date,
                    amount=parsed.amount,
                    merchant=parsed.merchant,
                    category=parsed.category,
                    type="expense",
                    notes=parsed.notes,
                ),
                source="web",
            )
            sheets.append_transaction(t)
            saved.append(t)

    # 2. Fetch all transactions (after saving, so new ones are included)
    transactions = sheets.get_all_transactions()
    tx_json = json.dumps([
        {"date": str(t.date), "amount": t.amount, "merchant": t.merchant,
         "category": t.category, "type": t.type}
        for t in transactions
    ])

    # 3. Build system prompt with transaction context and save summary
    system = _SYSTEM + f"\n\nTransaction data: {tx_json}"
    if saved:
        summary = ", ".join(f"${t.amount:.2f} at {t.merchant} [{t.category}] on {t.date}" for t in saved)
        system += f"\n\nJust saved {len(saved)} expense(s): {summary}."
    if skipped_count:
        system += f" Skipped {skipped_count} duplicate(s)."

    # 4. Build message list from history + new message
    messages = [{"role": m.role, "content": m.content} for m in request_body.history[-20:]]
    messages.append({"role": "user", "content": request_body.message})

    # 5. Call Claude
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=system,
        messages=messages,
    )
    reply = response.content[0].text

    # 6. Log usage
    log_usage(response, "chat")

    return ChatResponse(reply=reply)
```

- [ ] **Step 4: Register the chat router in `main.py`**

In `finances/backend/main.py`, add the import with the other router imports:

```python
from backend.chat import router as chat_router
```

And register it after the other routers:

```python
app.include_router(chat_router, dependencies=[Depends(_require_auth)])
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd finances
pytest tests/test_chat.py -v
```

Expected: 3 tests `PASSED`

- [ ] **Step 6: Run full test suite**

```bash
pytest -v
```

Expected: all 22 tests pass.

- [ ] **Step 7: Commit**

```bash
git add finances/backend/chat.py finances/tests/test_chat.py finances/backend/main.py
git commit -m "feat: add POST /api/chat endpoint with expense parsing and Claude insights"
```

---

## Task 4: Frontend Types and API Client

**Files:**
- Modify: `finances/frontend/src/types.ts`
- Modify: `finances/frontend/src/api.ts`

- [ ] **Step 1: Add `ChatMessage` to `types.ts`**

In `finances/frontend/src/types.ts`, append at the end:

```typescript
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
```

- [ ] **Step 2: Add `chat()` to `api.ts`**

In `finances/frontend/src/api.ts`, update the import line at the top:

```typescript
import type { Transaction, TransactionCreate, Category, ImportPreviewRow, ImportPreviewError, ChatMessage } from "./types";
```

Inside the `api` object, add after `importConfirm`:

```typescript
  chat: (message: string, history: ChatMessage[]) =>
    req<{ reply: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, history }),
    }),
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd finances/frontend
npx tsc --noEmit
```

Expected: no output (zero errors).

- [ ] **Step 4: Commit**

```bash
git add finances/frontend/src/types.ts finances/frontend/src/api.ts
git commit -m "feat: add ChatMessage type and chat API method"
```

---

## Task 5: Dark Theme CSS and App Router

**Files:**
- Modify: `finances/frontend/src/index.css`
- Modify: `finances/frontend/src/App.tsx`

- [ ] **Step 1: Replace `index.css` with dark theme**

Replace the entire contents of `finances/frontend/src/index.css`:

```css
:root {
  --bg: #0f172a;
  --surface: #1e293b;
  --border: #334155;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #6366f1;
  --income: #34d399;
  --expense: #f87171;
}

*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 16px;
  background: var(--bg);
  color: var(--text-primary);
}

nav {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0.75rem 1.25rem;
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  align-items: center;
}

nav a { text-decoration: none; color: var(--text-secondary); font-weight: 500; transition: color 0.15s; }
nav a:hover { color: var(--text-primary); }
nav a.active { color: var(--accent); border-bottom: 2px solid var(--accent); padding-bottom: 2px; }
.nav-logo { color: var(--accent); font-weight: 700; font-size: 1.1rem; letter-spacing: -0.5px; }

main { padding: 1.5rem; }

input, select, button, textarea { font-size: 16px; font-family: inherit; }

table { width: 100%; border-collapse: collapse; }
th {
  color: var(--text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}
th, td { padding: 0.625rem 0.5rem; text-align: left; }
thead tr { border-bottom: 1px solid var(--border); }
tbody tr { border-bottom: 1px solid var(--bg); color: var(--text-primary); }
tbody tr:hover { background: var(--surface); }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem;
}

.summary-cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.summary-cards .card { flex: 1; min-width: 140px; }

button {
  cursor: pointer;
  padding: 0.5rem 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text-primary);
  transition: opacity 0.15s;
}

button[type="submit"], button.primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

button:disabled { opacity: 0.45; cursor: not-allowed; }

input[type="text"], input[type="number"], input[type="date"],
input[type="month"], select, textarea {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-top: 0.25rem;
  background: var(--surface);
  color: var(--text-primary);
}

input::placeholder, textarea::placeholder { color: var(--text-muted); }
select option { background: var(--surface); }

label { display: block; margin-bottom: 0.75rem; font-weight: 500; color: var(--text-secondary); font-size: 0.9rem; }

h1 { color: var(--text-primary); margin-top: 0; }
h2 { color: var(--text-primary); }
h3 { color: var(--text-primary); }
p { color: var(--text-secondary); }
code {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-size: 0.875em;
  color: var(--text-secondary);
}

.amount-income { color: var(--income); }
.amount-expense { color: var(--expense); }
```

- [ ] **Step 2: Update `App.tsx` to add Chat route and logo**

Replace the entire contents of `finances/frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import TransactionList from "./components/TransactionList";
import AddTransaction from "./components/AddTransaction";
import CsvImport from "./components/CsvImport";
import CategoryManager from "./components/CategoryManager";
import Chat from "./components/Chat";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <span className="nav-logo">cleo</span>
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/transactions">Transactions</NavLink>
        <NavLink to="/chat">✦ Chat</NavLink>
        <NavLink to="/add">Add</NavLink>
        <NavLink to="/import">Import CSV</NavLink>
        <NavLink to="/categories">Categories</NavLink>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<TransactionList />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/add" element={<AddTransaction />} />
          <Route path="/import" element={<CsvImport />} />
          <Route path="/categories" element={<CategoryManager />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd finances/frontend
npx tsc --noEmit
```

Expected: error about missing `Chat` module (Chat.tsx doesn't exist yet) — that's expected and will be fixed in Task 6.

- [ ] **Step 4: Commit**

```bash
git add finances/frontend/src/index.css finances/frontend/src/App.tsx
git commit -m "feat: apply dark minimal theme and add Chat route to nav"
```

---

## Task 6: Chat Component

**Files:**
- Create: `finances/frontend/src/components/Chat.tsx`

- [ ] **Step 1: Create `Chat.tsx`**

Create `finances/frontend/src/components/Chat.tsx`:

```tsx
import { useState, useEffect, useRef } from "react";
import { api } from "../api";
import type { ChatMessage } from "../types";

const STORAGE_KEY = "cleo_chat_history";

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const history = [...messages];
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const { reply } = await api.chat(text, history);
      setMessages(prev => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "Something went wrong. Please try again.",
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      send();
    }
  };

  const clearHistory = () => {
    if (!confirm("Clear chat history?")) return;
    setMessages([]);
  };

  return (
    <div style={{
      maxWidth: 720,
      margin: "0 auto",
      display: "flex",
      flexDirection: "column",
      height: "calc(100vh - 100px)",
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        paddingBottom: "1rem",
        borderBottom: "1px solid var(--border)",
        marginBottom: "1rem",
      }}>
        <h1 style={{ margin: 0 }}>✦ Chat</h1>
        <button onClick={clearHistory} style={{
          background: "none",
          border: "1px solid var(--border)",
          color: "var(--text-muted)",
          borderRadius: 6,
          padding: "0.25rem 0.75rem",
          fontSize: "0.85rem",
        }}>
          Clear history
        </button>
      </div>

      <div style={{
        flex: 1,
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        paddingBottom: "0.5rem",
      }}>
        {messages.length === 0 && (
          <p style={{ textAlign: "center", marginTop: "3rem", color: "var(--text-muted)" }}>
            Paste expenses or ask anything about your finances.<br />
            <span style={{ fontSize: "0.85rem" }}>e.g. "Stanford FCU charge $15.66 at The Brazilian Spot" or "how much did I spend on food this month?"</span>
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "75%",
              padding: "0.75rem 1rem",
              borderRadius: msg.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
              background: msg.role === "user" ? "#312e81" : "var(--surface)",
              border: msg.role === "assistant" ? "1px solid var(--border)" : "none",
              color: msg.role === "user" ? "#e2e8f0" : "var(--text-secondary)",
              fontSize: "0.9rem",
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div style={{
              padding: "0.75rem 1rem",
              borderRadius: "12px 12px 12px 2px",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              fontSize: "1.2rem",
              letterSpacing: 4,
            }}>
              ···
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: "0.75rem" }}>
        <div style={{
          display: "flex",
          gap: "0.75rem",
          alignItems: "flex-end",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: "0.75rem",
        }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Paste expenses or ask anything... (Cmd+Enter to send)"
            rows={2}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text-primary)",
              fontSize: "0.9rem",
              resize: "none",
              maxHeight: 200,
              width: "auto",
              margin: 0,
              padding: 0,
            }}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            style={{
              background: "var(--accent)",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "0.5rem 1.25rem",
              fontWeight: 600,
              fontSize: "0.9rem",
              flexShrink: 0,
            }}
          >
            Send ↑
          </button>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", margin: "0.25rem 0 0", textAlign: "right" }}>
          Cmd+Enter to send
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd finances/frontend
npx tsc --noEmit
```

Expected: no output (zero errors).

- [ ] **Step 3: Start dev server and test the chat view**

```bash
# Terminal 1 — backend
cd finances && uvicorn backend.main:app --reload

# Terminal 2 — frontend
cd finances/frontend && npm run dev
```

Open http://localhost:5173/chat. Verify:
- Dark background and nav render correctly
- "✦ Chat" appears in nav and is active
- Empty state message shows
- You can type in the textarea
- Cmd+Enter submits
- Send button works
- Loading dots appear while waiting
- Response bubbles appear correctly

- [ ] **Step 4: Commit**

```bash
git add finances/frontend/src/components/Chat.tsx
git commit -m "feat: add Chat component with localStorage history and dark bubble UI"
```

---

## Task 7: Update Existing Components to Dark Theme

**Files:**
- Modify: `finances/frontend/src/components/Dashboard.tsx`
- Modify: `finances/frontend/src/components/TransactionList.tsx`
- Modify: `finances/frontend/src/components/AddTransaction.tsx`
- Modify: `finances/frontend/src/components/CsvImport.tsx`
- Modify: `finances/frontend/src/components/CategoryManager.tsx`

- [ ] **Step 1: Update `Dashboard.tsx`**

Replace the Recharts colors and inline text styles. Full file:

```tsx
import { useEffect, useState } from "react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "../api";
import type { Transaction } from "../types";

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
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Income</div>
          <div className="amount-income" style={{ fontSize: "1.75rem", fontWeight: 700 }}>
            ${totalIncome.toFixed(2)}
          </div>
        </div>
        <div className="card">
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Expenses</div>
          <div className="amount-expense" style={{ fontSize: "1.75rem", fontWeight: 700 }}>
            ${totalExpenses.toFixed(2)}
          </div>
        </div>
        <div className="card">
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Net</div>
          <div
            className={net >= 0 ? "amount-income" : "amount-expense"}
            style={{ fontSize: "1.75rem", fontWeight: 700 }}
          >
            {net >= 0 ? "+" : ""}${net.toFixed(2)}
          </div>
        </div>
      </div>

      <h2>Spending by category</h2>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={categoryData} margin={{ left: 10 }}>
            <XAxis dataKey="category" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={(v) => `$${Number(v).toFixed(2)}`}
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }}
            />
            <Bar dataKey="amount" fill="#6366f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <h2>6-month trend</h2>
      <div className="card">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={trendData} margin={{ left: 10 }}>
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={(v) => `$${Number(v).toFixed(2)}`}
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }}
            />
            <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
            <Line type="monotone" dataKey="expenses" stroke="#f87171" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="income" stroke="#34d399" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update `TransactionList.tsx`**

Replace the full file:

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
        <input type="month" value={month} onChange={e => setMonth(e.target.value)} style={{ width: "auto" }} />
        <select value={type} onChange={e => setType(e.target.value as typeof type)} style={{ width: "auto" }}>
          <option value="all">All types</option>
          <option value="income">Income</option>
          <option value="expense">Expense</option>
        </select>
        <select value={category} onChange={e => setCategory(e.target.value)} style={{ width: "auto" }}>
          <option value="all">All categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {filtered.length === 0
        ? <p>No transactions for this period.</p>
        : (
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th><th>Merchant</th><th>Category</th>
                  <th style={{ textAlign: "right" }}>Amount</th><th>Type</th><th>Source</th><th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(t => (
                  <tr key={t.id}>
                    <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{t.date}</td>
                    <td>{t.merchant}</td>
                    <td style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>{t.category}</td>
                    <td style={{ textAlign: "right" }} className={t.type === "income" ? "amount-income" : "amount-expense"}>
                      {t.type === "income" ? "+" : "-"}${t.amount.toFixed(2)}
                    </td>
                    <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{t.type}</td>
                    <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{t.source}</td>
                    <td>
                      <button
                        onClick={() => handleDelete(t.id)}
                        style={{ background: "none", border: "none", color: "var(--expense)", padding: "0 0.25rem", fontSize: "1rem" }}
                      >×</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
    </div>
  );
}
```

- [ ] **Step 3: Update `AddTransaction.tsx`**

Replace the full file:

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
      {error && <p className="amount-expense">{error}</p>}
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

- [ ] **Step 4: Update `CsvImport.tsx`**

Replace the full file:

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
      <p style={{ fontSize: "0.875rem" }}>Date format: YYYY-MM-DD. Type: <code>income</code> or <code>expense</code>.</p>

      {error && <p className="amount-expense">{error}</p>}
      {result && <p className="amount-income">{result}</p>}

      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "1rem" }}>
        <input type="file" accept=".csv" style={{ width: "auto", marginTop: 0 }}
          onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null); setResult(null); }} />
        <button onClick={handlePreview} disabled={!file} style={{ width: "auto" }}>Preview</button>
      </div>

      {preview && (
        <>
          {preview.errors.length > 0 && (
            <div style={{
              background: "var(--surface)",
              border: "1px solid var(--expense)",
              borderRadius: 6,
              padding: "0.75rem",
              marginBottom: "1rem",
            }}>
              <strong style={{ color: "var(--expense)" }}>Rows with errors (skipped):</strong>
              {preview.errors.map(e => (
                <div key={e.row} style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                  Row {e.row}: {e.reason}
                </div>
              ))}
            </div>
          )}

          <h3>{preview.valid_rows.length} valid rows</h3>
          <div className="card" style={{ padding: 0, overflow: "hidden", marginBottom: "1rem" }}>
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
                    <td style={{ textAlign: "right" }} className="amount-expense">${r.amount.toFixed(2)}</td>
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
          >
            {importing ? "Importing…" : `Import ${preview.valid_rows.length} transactions`}
          </button>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Update `CategoryManager.tsx`**

Replace the full file:

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
      {error && <p className="amount-expense">{error}</p>}

      <h2>Predefined</h2>
      <ul style={{ paddingLeft: "1.25rem", color: "var(--text-secondary)" }}>
        {predefined.map(c => <li key={c.name} style={{ marginBottom: "0.25rem" }}>{c.name}</li>)}
      </ul>

      <h2>Custom</h2>
      {custom.length === 0 && <p style={{ color: "var(--text-muted)" }}>No custom categories yet.</p>}
      <ul style={{ paddingLeft: "1.25rem" }}>
        {custom.map(c => (
          <li key={c.name} style={{
            display: "flex",
            gap: "0.5rem",
            alignItems: "center",
            marginBottom: "0.25rem",
            color: "var(--text-primary)",
          }}>
            {c.name}
            <button onClick={() => handleDelete(c.name)}
              style={{ color: "var(--expense)", border: "none", background: "none", padding: "0 0.25rem", fontSize: "1.1rem", cursor: "pointer" }}>
              ×
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={handleAdd} style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
        <input
          type="text"
          placeholder="New category name"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          style={{ flex: 1, marginTop: 0 }}
        />
        <button type="submit" className="primary" style={{ width: "auto" }}>Add</button>
      </form>
    </div>
  );
}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd finances/frontend
npx tsc --noEmit
```

Expected: no output (zero errors).

- [ ] **Step 7: Visual check — open the app and walk through every page**

```bash
cd finances/frontend && npm run dev
```

Check each route:
- `/` — Dashboard: dark cards, indigo bars, green income / red expenses
- `/transactions` — dark table with correct amount colors
- `/add` — dark form inputs and labels
- `/import` — dark file input and table
- `/categories` — dark list, correct button colors
- `/chat` — chat bubbles, textarea, loading state

- [ ] **Step 8: Commit**

```bash
git add finances/frontend/src/components/
git commit -m "feat: update all components to dark minimal theme"
```

---

## Task 8: Deploy

- [ ] **Step 1: Run full test suite**

```bash
cd finances
pytest -v
```

Expected: 22 tests pass.

- [ ] **Step 2: Push to trigger Render deploy**

```bash
git push origin main
```

- [ ] **Step 3: Verify on production**

- Open https://cleo-finance.onrender.com
- Sign in — should redirect to dark dashboard
- Open Chat, paste a Stanford FCU SMS block
- Verify transactions are saved to Google Sheets
- Ask "how much did I spend on transport this month?" — verify Claude answers with correct data
- Check the Logs tab in Google Sheets — rows should appear for each API call
