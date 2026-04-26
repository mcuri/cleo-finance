# Financial Profile Extractor — Design Spec

**Date:** 2026-04-25
**Status:** Approved

---

## Overview

After each chat response, fire an async lightweight Claude Haiku call that reads the exchange (user message + Cleo reply), infers behavioral financial patterns, and updates a persistent user profile in `finances/user-finance-notes.md`. The profile is included in the chat system prompt so Cleo personalizes responses over time.

---

## Goals

- Build a living behavioral profile of the user's financial habits, concerns, and patterns
- Personalize Cleo's responses based on observed patterns (e.g., knows the user is savings-conscious)
- Never block a chat response — extraction is fire-and-forget
- Never crash silently or corrupt the notes file

---

## File Structure: `user-finance-notes.md`

Two new managed sections are appended at the bottom of the existing file (after the code summary entries). Existing content is never modified.

```markdown
---

## Current Profile
_Last updated: YYYY-MM-DD_

- Tends to track restaurant spending frequently; may be budget-conscious about dining out
- Has mentioned saving goals in multiple conversations
- Income appears to be payslip-based (salaried)

---

## Observations Log

- **2026-04-25**: First payslip uploaded — salaried income confirmed; asked about savings rate
- **2026-04-24**: Mentioned eating out "too much" — suggests awareness of a spending habit
```

- `## Current Profile` — fully rewritten on each update; contains synthesized behavioral bullet points
- `## Observations Log` — append-only; one dated line per update
- Both sections are absent until the first update occurs

---

## New File: `finances/backend/profile_extractor.py`

Two functions:

### `async def extract_and_update_profile(user_message: str, assistant_reply: str) -> None`

1. Reads `user-finance-notes.md`, extracts the current `## Current Profile` section (empty string if not yet present)
2. Calls Claude Haiku synchronously via `asyncio.get_event_loop().run_in_executor(None, ...)` to avoid blocking the event loop
3. Prompt includes:
   - The current exchange (user message + assistant reply)
   - The current profile (so patterns can be refined, not just added)
   - Instruction to return JSON only: `{"update": false}` or `{"update": true, "profile": "...", "log_entry": "..."}`
   - Instruction to set `update: false` if the exchange contains no new financial signal (small talk, balance queries, etc.)
4. If `update: true`:
   - Rewrites the `## Current Profile` block (with updated `_Last updated_` date)
   - Appends a dated entry to `## Observations Log`
5. On any exception (JSON parse error, file I/O error, API error): logs a warning and returns — never raises

### `def load_user_profile() -> str`

- Reads `user-finance-notes.md`
- Returns the content of the `## Current Profile` section (between the heading and the next `---`)
- Returns `""` if the section doesn't exist yet or the file doesn't exist

---

## Changes to `finances/backend/chat.py`

### 1. Fire extraction after each response

After `reply = response.content[0].text` (currently line 291):

```python
import asyncio
from backend.profile_extractor import extract_and_update_profile

asyncio.create_task(extract_and_update_profile(message, reply))
```

### 2. Include profile in system prompt

After building the base `system` string (before the Claude call):

```python
from backend.profile_extractor import load_user_profile

profile = load_user_profile()
if profile:
    system += f"\n\nUser financial profile (behavioral patterns observed over time):\n{profile}"
```

---

## Claude Extraction Prompt (template)

```
You are a financial behavior analyst. Read the following conversation exchange and the current user profile, then decide if there is new financial signal worth recording.

Current profile:
{profile}

Exchange:
User: {user_message}
Assistant: {assistant_reply}

Return JSON only. No explanation. Either:
  {"update": false}
if there is no new financial signal (e.g. balance queries, small talk, duplicate patterns already in profile), or:
  {"update": true, "profile": "<full rewritten profile as bullet points>", "log_entry": "<one-line dated observation>"}
if a new behavioral pattern, goal, habit, or financial fact emerges.

Profile bullet points should describe patterns and tendencies — not one-off facts. Refine existing bullets rather than duplicating them.
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Claude returns malformed JSON | Log warning, return — profile unchanged |
| `user-finance-notes.md` missing | `load_user_profile` returns `""`; extractor creates the sections on first update |
| File I/O error during write | Log warning, return — never raises |
| API error during extraction | Log warning, return — chat response already delivered |
| `update: false` returned | No file write, no-op |

---

## Out of Scope

- Showing the profile in the UI
- Letting the user edit or reset the profile via chat
- Running extraction on Telegram messages (chat endpoint only)
- Backfilling profile from existing transaction history

---

## File Map

| File | Change |
|------|--------|
| `finances/backend/profile_extractor.py` | **Create** — `extract_and_update_profile` + `load_user_profile` |
| `finances/backend/chat.py` | Fire extraction task after reply; prepend profile to system prompt |
| `finances/user-finance-notes.md` | New `## Current Profile` and `## Observations Log` sections added at runtime |
