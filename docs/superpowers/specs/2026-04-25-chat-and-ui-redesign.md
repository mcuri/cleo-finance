# Chat View & UI Redesign — Design Spec

**Date:** 2026-04-25
**Status:** Approved

---

## Overview

Two changes shipped together:

1. **UI Redesign** — replace the current unstyled look with a dark, minimal theme (dark background, slate card surfaces, indigo accents, emerald/red for income/expenses).
2. **Chat View** — a new full-page conversational interface where the user can paste bulk expenses and ask freeform questions about their finances.

---

## UI Redesign

### Color Palette

CSS variables defined in `index.css`:

| Variable | Value | Usage |
|---|---|---|
| `--bg` | `#0f172a` | Page background |
| `--surface` | `#1e293b` | Cards, inputs, nav |
| `--border` | `#334155` | Card borders |
| `--text-primary` | `#e2e8f0` | Main text |
| `--text-secondary` | `#94a3b8` | Labels, subtitles |
| `--text-muted` | `#475569` | Placeholders |
| `--accent` | `#6366f1` | Indigo — active nav, buttons, user bubbles |
| `--income` | `#34d399` | Emerald — income amounts |
| `--expense` | `#f87171` | Red — expense amounts |

### Scope

- `index.css` — new CSS variables + global dark base styles
- `App.tsx` — nav styled with dark theme, active link highlighted with indigo underline
- All 5 existing components updated to use CSS variables (no hardcoded colors)

---

## Chat View

### Route

`/chat` — added to `App.tsx` router and nav as "✦ Chat"

### Component: `Chat.tsx`

**Layout:**
- Full-height flex column: message list (scrollable, flex-grow) + input bar (fixed bottom)
- User messages: right-aligned, indigo background (`#312e81`), rounded `12px 12px 2px 12px`
- Assistant messages: left-aligned, surface card background, border, rounded `12px 12px 12px 2px`
- Date separator shown when day changes

**Conversation history:**
- Stored in `localStorage` under key `cleo_chat_history`
- Format: `Array<{ role: "user" | "assistant", content: string }>`
- Loaded on mount, updated after each exchange
- "Clear history" button in the header

**Input:**
- `<textarea>` (multi-line) — supports pasting long SMS blocks
- Submit on `Cmd/Ctrl+Enter` or Send button
- Disabled while waiting for response
- Loading indicator (animated dots) shown as a temporary assistant bubble

### Backend: `POST /api/chat`

**Request:**
```json
{
  "message": "string",
  "history": [{ "role": "user" | "assistant", "content": "string" }]
}
```

**Response:**
```json
{ "reply": "string" }
```

**Handler logic (`backend/chat.py`):**

1. Run `parse_expense_text(message)` to detect embedded expenses
2. For each parsed expense with confidence ≥ 0.5:
   - Check for duplicate via `find_duplicate`
   - Save non-duplicates via `append_transaction`
   - Collect saved and skipped lists
3. Fetch all transactions from Sheets via `SheetsClient` (after saving, so new ones are included)
4. Build Claude prompt:
   - **System:** "You are Cleo, a personal finance assistant. Answer questions about the user's transactions. Be concise and specific. If expenses were just saved, acknowledge them first."
   - **Context block:** all transactions serialized as JSON (injected as first user turn, cached)
   - **Conversation history:** last 20 turns
   - **New user message:** the raw input
5. Call Claude Haiku, return `reply`

**Model:** `claude-haiku-4-5-20251001`
**Max tokens:** 512
**Auth:** protected by `require_auth` dependency

### New config field

`backend/config.py` already has all required fields. No new env vars needed.

---

## Data Flow

```
User pastes SMS / asks question
       ↓
POST /api/chat { message, history }
       ↓
Parse for expenses → save new ones to Sheets
       ↓
Fetch all transactions from Sheets
       ↓
Build prompt: system + transactions context + history + message
       ↓
Claude Haiku → reply
       ↓
{ reply } → Chat.tsx → append bubble + update localStorage
```

---

## Anthropic API Logging

Every call to the Anthropic API (chat, expense parsing, receipt parsing) is logged to stdout in a structured format so Render's log viewer shows them clearly:

```
[anthropic] model=claude-haiku-4-5-20251001 input_tokens=1234 output_tokens=87 endpoint=chat
```

Implementation: a thin `_log_usage(response, endpoint)` helper in `backend/claude_parser.py` and `backend/chat.py` that reads `response.usage` after each `client.messages.create` call and logs via Python's standard `logging` module at `INFO` level.

No new dependencies required.

---

## Out of Scope

- Streaming responses (reply arrives all at once)
- Editing or deleting messages from the chat
- Exporting chat history
- Mobile-specific layout changes (existing responsive CSS carries over)
