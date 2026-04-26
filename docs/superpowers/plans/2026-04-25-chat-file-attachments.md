# Chat File Attachments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users paste images and upload bank-statement PDFs in the Chat view — files are sent to the backend, expenses extracted and saved to Sheets, and Claude responds naturally in the thread.

**Architecture:** The `/api/chat` endpoint switches from JSON body to `multipart/form-data`. A new `parse_pdf_statement` function in `claude_parser.py` sends PDFs to Claude as a document content block (Anthropic natively supports this). A shared `_save_expenses` helper handles duplicate-checking and Sheets writes for all three input paths (text, image, PDF). The frontend adds a clipboard paste handler, a 📎 file button, an attachment preview, and always sends `FormData`.

**Tech Stack:** FastAPI `Form`/`UploadFile`, Anthropic Messages API (image + document content blocks), React 19 + TypeScript 6, `FormData` browser API.

---

## Task 1: `parse_pdf_statement` in `claude_parser.py`

**Files:**
- Modify: `finances/backend/claude_parser.py`
- Modify: `finances/tests/test_claude_parser.py`

Context: `claude_parser.py` already has `parse_receipt_image` (image → `List[ParsedExpense]`). This task adds an identical function for PDFs using the Anthropic `document` content block type. The existing `_parse_response`, `_JSON_SCHEMA`, `_TEXT_SYSTEM`, `_CATEGORIES`, `_MODEL`, and `log_usage` are all reused.

- [ ] **Step 1: Add failing tests for `parse_pdf_statement`**

Open `finances/tests/test_claude_parser.py`. The file currently imports `parse_expense_text, parse_receipt_image`. Add `parse_pdf_statement` to the import and append these two tests at the end:

```python
from backend.claude_parser import parse_expense_text, parse_receipt_image, parse_pdf_statement

# ... existing tests unchanged ...

def test_parse_pdf_statement_returns_parsed_expenses():
    with patch("backend.claude_parser._client") as mock_client, \
         patch("backend.claude_parser.log_usage"):
        mock_client.messages.create.return_value = _mock_response(f"[{VALID_JSON}]")
        result = parse_pdf_statement(b"fake-pdf-bytes")
    assert len(result) == 1
    assert result[0].amount == 100.0
    assert result[0].merchant == "Trader Joe's"


def test_parse_pdf_statement_malformed_json_returns_empty_list():
    with patch("backend.claude_parser._client") as mock_client, \
         patch("backend.claude_parser.log_usage"):
        mock_client.messages.create.return_value = _mock_response("not valid json at all")
        result = parse_pdf_statement(b"fake-pdf-bytes")
    assert result == []
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd finances
python3 -m pytest tests/test_claude_parser.py::test_parse_pdf_statement_returns_parsed_expenses tests/test_claude_parser.py::test_parse_pdf_statement_malformed_json_returns_empty_list -v
```

Expected: `ImportError: cannot import name 'parse_pdf_statement'`

- [ ] **Step 3: Add `parse_pdf_statement` to `claude_parser.py`**

Add this function after `parse_receipt_image` (before `_parse_response`):

```python
def parse_pdf_statement(pdf_bytes: bytes) -> List[ParsedExpense]:
    schema = _JSON_SCHEMA.format(cats=", ".join(_CATEGORIES))
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    response = _client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        system=_TEXT_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                {"type": "text",
                 "text": (
                     f"Extract all expense transactions and return a JSON array matching: {schema}\n\n"
                     f"Today is {date.today().isoformat()}. Use today for any missing dates."
                 )},
            ],
        }],
    )
    log_usage(response, "parse_pdf_statement")
    return _parse_response(response.content[0].text)
```

- [ ] **Step 4: Run all parser tests — expect 9 passing**

```bash
python3 -m pytest tests/test_claude_parser.py -v
```

Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add finances/backend/claude_parser.py finances/tests/test_claude_parser.py
git commit -m "feat: add parse_pdf_statement to claude_parser"
```

---

## Task 2: Refactor `chat.py` — form data + file routing

**Files:**
- Modify: `finances/backend/chat.py`
- Modify: `finances/tests/test_chat.py`

Context: `chat.py` currently accepts a JSON body (`ChatRequest` Pydantic model). This task rewrites it to accept `multipart/form-data` and routes image/PDF files to the appropriate parsers. A `_save_expenses` helper is extracted to remove duplication.

- [ ] **Step 1: Update `test_chat.py` — change existing tests to form data and add 2 file tests**

Replace the entire file:

```python
import io
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


def _mock_claude(mock_cls, text="OK"):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text)]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=10)
    mock_response.model = "claude-haiku-4-5-20251001"
    mock_cls.return_value.messages.create.return_value = mock_response


def test_chat_returns_reply(client):
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "You have no transactions yet.")
        resp = client.post("/api/chat", data={"message": "hello", "history": "[]"})

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
        _mock_claude(mock_cls, "Saved 1 expense.")
        resp = client.post("/api/chat", data={
            "message": "Stanford FCU charge $15.66 at The Brazilian Spot",
            "history": "[]",
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
        _mock_claude(mock_cls, "Skipped duplicate.")
        resp = client.post("/api/chat", data={
            "message": "Stanford FCU charge $15.66 at The Brazilian Spot",
            "history": "[]",
        })

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_not_called()


def test_chat_with_image_file(client, mock_sheets):
    from backend.models import ParsedExpense
    parsed = ParsedExpense(amount=25.0, merchant="Whole Foods", category="Groceries", confidence=0.9)
    with patch("backend.chat.parse_receipt_image", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Saved receipt.")
        resp = client.post("/api/chat",
            data={"message": "what's on this receipt?", "history": "[]"},
            files={"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_called_once()


def test_chat_with_pdf_file(client, mock_sheets):
    from backend.models import ParsedExpense
    parsed = [
        ParsedExpense(amount=50.0, merchant="Amazon", category="Shopping", confidence=0.9),
        ParsedExpense(amount=12.0, merchant="Netflix", category="Subscriptions", confidence=0.9),
    ]
    with patch("backend.chat.parse_pdf_statement", return_value=parsed), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Saved 2 transactions from statement.")
        resp = client.post("/api/chat",
            data={"message": "import this statement", "history": "[]"},
            files={"file": ("statement.pdf", b"fake-pdf-bytes", "application/pdf")},
        )

    assert resp.status_code == 200
    assert mock_sheets.append_transaction.call_count == 2
```

- [ ] **Step 2: Run tests — expect failures**

```bash
python3 -m pytest tests/test_chat.py -v
```

Expected: failures because `chat.py` still expects JSON and doesn't have `parse_pdf_statement` import.

- [ ] **Step 3: Replace `chat.py` with new implementation**

Replace the entire file:

```python
import base64
import json
import logging
from datetime import date as date_type
from typing import List, Optional, Tuple

import anthropic
import backend.chat as _self
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.anthropic_logger import log_usage
from backend.claude_parser import parse_expense_text, parse_pdf_statement, parse_receipt_image
from backend.config import get_settings
from backend.models import ParsedExpense, Transaction, TransactionCreate
from backend.sheets import SheetsClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

_MODEL = "claude-haiku-4-5-20251001"
_SYSTEM = (
    "You are Cleo, a personal finance assistant backed by a real app. "
    "When the user sends a message, the backend ALREADY automatically extracted and saved any "
    "parseable expenses before this conversation turn. "
    "NEVER tell the user to save their data manually or that you cannot save — saving is handled "
    "automatically by the backend. "
    "If a save summary appears below, confirm what was saved. "
    "If no expenses were detected, tell the user what formats work best "
    "(e.g. 'spent $X at Place on Category'). "
    "Answer questions about their transaction history concisely using the data below. "
    "Be brief — 2-4 sentences max unless detail is needed."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    reply: str


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=get_settings().google_sheets_id)


def _get_sheets_client():
    return _self.get_sheets_client()


def _save_expenses(
    parsed_list: List[ParsedExpense],
    sheets: SheetsClient,
) -> Tuple[List[Transaction], int]:
    saved: List[Transaction] = []
    skipped = 0
    for parsed in parsed_list:
        expense_date = parsed.date or date_type.today()
        if sheets.find_duplicate(expense_date, parsed.amount, parsed.merchant):
            skipped += 1
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
    return saved, skipped


@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    history: str = Form("[]"),
    file: Optional[UploadFile] = File(None),
    sheets: SheetsClient = Depends(_get_sheets_client),
):
    history_list = [ChatMessage(**m) for m in json.loads(history)]

    # 1. Parse expenses and build user content block
    saved: List[Transaction] = []
    skipped_count = 0
    user_content: object = message

    if file:
        file_bytes = await file.read()
        b64 = base64.standard_b64encode(file_bytes).decode()
        ct = file.content_type or ""
        if ct.startswith("image/"):
            saved, skipped_count = _save_expenses(parse_receipt_image(file_bytes, ct), sheets)
            file_block = {"type": "image", "source": {"type": "base64", "media_type": ct, "data": b64}}
        elif ct == "application/pdf":
            saved, skipped_count = _save_expenses(parse_pdf_statement(file_bytes), sheets)
            file_block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Send an image or PDF.")
        user_content = [file_block, {"type": "text", "text": message}]
    else:
        saved, skipped_count = _save_expenses(parse_expense_text(message), sheets)

    # 2. Fetch all transactions (after saving)
    transactions = sheets.get_all_transactions()
    tx_json = json.dumps([
        {"date": str(t.date), "amount": t.amount, "merchant": t.merchant,
         "category": t.category, "type": t.type}
        for t in transactions
    ])

    # 3. Build system prompt
    system = _SYSTEM + f"\n\nTransaction data: {tx_json}"
    if saved:
        summary = ", ".join(
            f"${t.amount:.2f} at {t.merchant} [{t.category}] on {t.date}" for t in saved
        )
        system += f"\n\nJust saved {len(saved)} expense(s): {summary}."
    if skipped_count:
        system += f" Skipped {skipped_count} duplicate(s)."
    if not saved and not skipped_count:
        system += "\n\nNo expenses were detected in the user's latest message."

    # 4. Build messages list
    messages = [{"role": m.role, "content": m.content} for m in history_list[-20:]]
    messages.append({"role": "user", "content": user_content})

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

- [ ] **Step 4: Run all backend tests — expect 25 passing**

```bash
python3 -m pytest -v
```

Expected: `25 passed`

- [ ] **Step 5: Commit**

```bash
git add finances/backend/chat.py finances/tests/test_chat.py
git commit -m "feat: chat endpoint accepts multipart/form-data with optional image or PDF"
```

---

## Task 3: Frontend types and API client

**Files:**
- Modify: `finances/frontend/src/types.ts`
- Modify: `finances/frontend/src/api.ts`

- [ ] **Step 1: Add `attachment` field to `ChatMessage` in `types.ts`**

Replace the `ChatMessage` interface:

```ts
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  attachment?: { type: "image" | "pdf"; label: string; dataUrl?: string };
}
```

- [ ] **Step 2: Replace `api.chat` with `api.chatForm` in `api.ts`**

Replace this line:
```ts
  chat: (message: string, history: ChatMessage[]) =>
    req<{ reply: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, history }),
    }),
```

With:
```ts
  chatForm: (form: FormData) =>
    req<{ reply: string }>("/api/chat", { method: "POST", body: form }),
```

The `req` helper already skips `Content-Type` for `FormData` (see line 8: `!(options.body instanceof FormData)`), so no other changes needed.

- [ ] **Step 3: Build to verify TypeScript**

```bash
cd finances/frontend
npm run build
```

Expected: zero TypeScript errors.

- [ ] **Step 4: Commit**

```bash
cd ../..
git add finances/frontend/src/types.ts finances/frontend/src/api.ts
git commit -m "feat: add attachment type to ChatMessage and chatForm API method"
```

---

## Task 4: Update `Chat.tsx`

**Files:**
- Modify: `finances/frontend/src/components/Chat.tsx`

- [ ] **Step 1: Replace the entire file**

```tsx
import { useState, useEffect, useRef } from "react";
import { api } from "../api";
import type { ChatMessage } from "../types";

const STORAGE_KEY = "cleo_chat_history";
const MAX_FILE_BYTES = 10 * 1024 * 1024;

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
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [attachError, setAttachError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const attachFile = (file: File | null | undefined) => {
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setAttachError("File too large (max 10 MB).");
      return;
    }
    setAttachError("");
    setAttachedFile(file);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const file = e.clipboardData.files[0];
    if (file?.type.startsWith("image/")) {
      e.preventDefault();
      attachFile(file);
    }
  };

  const send = async () => {
    const text = input.trim();
    if ((!text && !attachedFile) || loading) return;

    let attachment: ChatMessage["attachment"] | undefined;
    if (attachedFile) {
      if (attachedFile.type.startsWith("image/")) {
        attachment = {
          type: "image",
          label: attachedFile.name,
          dataUrl: URL.createObjectURL(attachedFile),
        };
      } else {
        attachment = { type: "pdf", label: attachedFile.name };
      }
    }

    const userMsg: ChatMessage = {
      role: "user",
      content: text || "[File attached]",
      attachment,
    };
    const history = [...messages];
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    const fileToSend = attachedFile;
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setLoading(true);

    try {
      const form = new FormData();
      form.append("message", text || "[File attached]");
      form.append("history", JSON.stringify(history.map(m => ({ role: m.role, content: m.content }))));
      if (fileToSend) form.append("file", fileToSend);
      const { reply } = await api.chatForm(form);
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
    <div
      style={{ maxWidth: 720, margin: "0 auto", display: "flex", flexDirection: "column", height: "calc(100vh - 100px)" }}
      onPaste={handlePaste}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "1rem", borderBottom: "1px solid var(--border)", marginBottom: "1rem" }}>
        <h1 style={{ margin: 0 }}>✦ Chat</h1>
        <button onClick={clearHistory} style={{ background: "none", border: "1px solid var(--border)", color: "var(--text-muted)", borderRadius: 6, padding: "0.25rem 0.75rem", fontSize: "0.85rem" }}>
          Clear history
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.75rem", paddingBottom: "0.5rem" }}>
        {messages.length === 0 && (
          <p style={{ textAlign: "center", marginTop: "3rem", color: "var(--text-muted)" }}>
            Paste expenses, attach an image, or upload a bank statement PDF.<br />
            <span style={{ fontSize: "0.85rem" }}>Or ask anything about your finances.</span>
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
              {msg.attachment?.type === "image" && msg.attachment.dataUrl && (
                <img
                  src={msg.attachment.dataUrl}
                  alt="attachment"
                  style={{ maxWidth: 200, maxHeight: 150, borderRadius: 6, display: "block", marginBottom: "0.5rem" }}
                />
              )}
              {msg.attachment?.type === "pdf" && (
                <div style={{ fontSize: "0.8rem", color: "#a5b4fc", marginBottom: "0.25rem" }}>
                  📄 {msg.attachment.label}
                </div>
              )}
              {msg.content !== "[File attached]" && msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div style={{ padding: "0.75rem 1rem", borderRadius: "12px 12px 12px 2px", background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)", fontSize: "1.2rem", letterSpacing: 4 }}>
              ···
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: "0.75rem" }}>
        {attachError && (
          <p style={{ color: "var(--expense)", fontSize: "0.8rem", margin: "0 0 0.5rem" }}>{attachError}</p>
        )}
        {attachedFile && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            {attachedFile.type.startsWith("image/") ? (
              <img
                src={URL.createObjectURL(attachedFile)}
                alt="preview"
                style={{ height: 60, borderRadius: 6, border: "1px solid var(--border)" }}
              />
            ) : (
              <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", background: "var(--surface)", border: "1px solid var(--border)", padding: "0.25rem 0.5rem", borderRadius: 6 }}>
                📄 {attachedFile.name}
              </span>
            )}
            <button
              onClick={() => { setAttachedFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}
              style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1.1rem", padding: "0 0.25rem" }}
            >
              ×
            </button>
          </div>
        )}
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: "0.75rem" }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,application/pdf"
            style={{ display: "none" }}
            onChange={e => attachFile(e.target.files?.[0])}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            title="Attach image or PDF"
            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1.2rem", padding: "0 0.25rem", flexShrink: 0 }}
          >
            📎
          </button>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Paste expenses or ask anything... (Cmd+Enter to send)"
            rows={2}
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--text-primary)", fontSize: "0.9rem", resize: "none", maxHeight: 200, width: "auto", margin: 0, padding: 0 }}
          />
          <button
            onClick={send}
            disabled={loading || (!input.trim() && !attachedFile)}
            style={{ background: "var(--accent)", color: "#fff", border: "none", borderRadius: 8, padding: "0.5rem 1.25rem", fontWeight: 600, fontSize: "0.9rem", flexShrink: 0 }}
          >
            Send ↑
          </button>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", margin: "0.25rem 0 0", textAlign: "right" }}>
          Cmd+Enter to send · 📎 attach image or PDF
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build to verify TypeScript**

```bash
cd finances/frontend
npm run build
```

Expected: zero TypeScript errors, `✓ built in ~XXXms`.

- [ ] **Step 3: Smoke test in browser**

```bash
npm run dev
```

Open http://localhost:5173/chat and verify:
- Empty state hint text updated ("attach an image, or upload a bank statement PDF")
- 📎 button appears in input bar; click opens file picker accepting `image/*` and `application/pdf`
- Select an image → thumbnail preview appears with × to remove
- Select a PDF → filename chip appears with × to remove
- Paste an image from clipboard → thumbnail appears
- Try a file > 10 MB → error message "File too large (max 10 MB)." appears
- Send with image → image thumbnail appears in user bubble
- Send with PDF → `📄 filename.pdf` label appears in user bubble
- Send button disabled when input empty and no file attached

- [ ] **Step 4: Commit**

```bash
cd ../..
git add finances/frontend/src/components/Chat.tsx
git commit -m "feat: chat supports image paste and PDF upload with attachment preview"
```

- [ ] **Step 5: Push to deploy**

```bash
git push origin main
```
