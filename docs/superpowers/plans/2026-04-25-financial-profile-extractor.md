# Financial Profile Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After each chat response, fire an async lightweight Claude call that infers behavioral financial patterns from the exchange and updates a living profile in `user-finance-notes.md`, which is then included in the chat system prompt for personalization.

**Architecture:** New `profile_extractor.py` with two public functions (`load_user_profile`, `extract_and_update_profile`) that read and rewrite two managed sections (`## Current Profile`, `## Observations Log`) at the bottom of `user-finance-notes.md`. The `chat.py` endpoint fires the extraction as a fire-and-forget `asyncio.create_task` after delivering the reply, and prepends the loaded profile to the system prompt before each call.

**Tech Stack:** Python 3.11, asyncio, anthropic SDK (Claude Haiku), pathlib, pytest + pytest-asyncio

---

## File Map

| File | Change |
|------|--------|
| `finances/backend/profile_extractor.py` | **Create** — `load_user_profile`, `_write_profile_and_log`, `_call_claude_extract`, `extract_and_update_profile` |
| `finances/tests/test_profile_extractor.py` | **Create** — unit tests for all four functions |
| `finances/backend/chat.py` | **Modify** — add `import asyncio`, import new functions, prepend profile to system prompt, fire extraction task |
| `finances/tests/test_chat.py` | **Modify** — add tests for profile inclusion and extraction task firing |

---

### Task 1: `load_user_profile()` and `_write_profile_and_log()`

**Files:**
- Create: `finances/backend/profile_extractor.py`
- Create: `finances/tests/test_profile_extractor.py`

- [ ] **Step 1: Write failing tests for `load_user_profile`**

Create `finances/tests/test_profile_extractor.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import patch


def test_load_user_profile_returns_empty_when_file_missing(tmp_path):
    from backend.profile_extractor import load_user_profile
    assert load_user_profile(tmp_path / "missing.md") == ""


def test_load_user_profile_returns_empty_when_section_absent(tmp_path):
    from backend.profile_extractor import load_user_profile
    f = tmp_path / "notes.md"
    f.write_text("# Notes\n\nSome content\n")
    assert load_user_profile(f) == ""


def test_load_user_profile_returns_profile_content(tmp_path):
    from backend.profile_extractor import load_user_profile
    f = tmp_path / "notes.md"
    f.write_text(
        "# Notes\n\n---\n\n## Current Profile\n_Last updated: 2026-04-25_\n\n"
        "- Saves regularly\n- Dining out often\n\n---\n\n## Observations Log\n"
    )
    result = load_user_profile(f)
    assert "Saves regularly" in result
    assert "Dining out often" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd finances
pytest tests/test_profile_extractor.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.profile_extractor'`

- [ ] **Step 3: Create `profile_extractor.py` with `load_user_profile`**

Create `finances/backend/profile_extractor.py`:

```python
import asyncio
import json
import logging
from datetime import date as date_type
from pathlib import Path

import anthropic

from backend.config import get_settings

logger = logging.getLogger(__name__)

_NOTES_FILE = Path(__file__).parent.parent / "user-finance-notes.md"
_MODEL = "claude-haiku-4-5-20251001"
_PROFILE_HEADING = "## Current Profile"
_LOG_HEADING = "## Observations Log"


def load_user_profile(notes_file: Path = _NOTES_FILE) -> str:
    if not notes_file.exists():
        return ""
    content = notes_file.read_text()
    start = content.find(_PROFILE_HEADING)
    if start == -1:
        return ""
    section_start = content.find("\n", start) + 1
    if content[section_start:].startswith("_Last updated"):
        section_start = content.find("\n", section_start) + 1
    end = len(content)
    for marker in ["\n---", "\n## "]:
        pos = content.find(marker, section_start)
        if pos != -1 and pos < end:
            end = pos
    return content[section_start:end].strip()
```

- [ ] **Step 4: Run load_user_profile tests — expect PASS**

```bash
cd finances
pytest tests/test_profile_extractor.py::test_load_user_profile_returns_empty_when_file_missing tests/test_profile_extractor.py::test_load_user_profile_returns_empty_when_section_absent tests/test_profile_extractor.py::test_load_user_profile_returns_profile_content -v
```
Expected: 3 PASS

- [ ] **Step 5: Write failing tests for `_write_profile_and_log`**

Append to `finances/tests/test_profile_extractor.py`:

```python
def test_write_profile_and_log_creates_sections_when_absent(tmp_path):
    from backend.profile_extractor import _write_profile_and_log
    f = tmp_path / "notes.md"
    f.write_text("# Notes\n\nExisting content.\n")
    _write_profile_and_log("- New pattern", "First observation", f)
    content = f.read_text()
    assert "## Current Profile" in content
    assert "- New pattern" in content
    assert "## Observations Log" in content
    assert "First observation" in content


def test_write_profile_and_log_updates_existing_profile(tmp_path):
    from backend.profile_extractor import _write_profile_and_log
    f = tmp_path / "notes.md"
    f.write_text(
        "# Notes\n\n---\n\n## Current Profile\n_Last updated: 2026-04-24_\n\n"
        "- Old pattern\n\n---\n\n## Observations Log\n\n- **2026-04-24**: old entry\n"
    )
    _write_profile_and_log("- Updated pattern", "New entry today", f)
    content = f.read_text()
    assert "Updated pattern" in content
    assert "Old pattern" not in content
    assert "New entry today" in content
    assert "old entry" in content  # log is append-only


def test_write_profile_and_log_does_not_duplicate_heading(tmp_path):
    from backend.profile_extractor import _write_profile_and_log
    f = tmp_path / "notes.md"
    f.write_text(
        "# Notes\n\n---\n\n## Current Profile\n_Last updated: 2026-04-24_\n\n"
        "- Old pattern\n\n---\n\n## Observations Log\n\n- **2026-04-24**: old entry\n"
    )
    _write_profile_and_log("- Updated pattern", "New entry today", f)
    content = f.read_text()
    assert content.count("## Current Profile") == 1
```

- [ ] **Step 6: Run write tests — expect FAIL**

```bash
cd finances
pytest tests/test_profile_extractor.py::test_write_profile_and_log_creates_sections_when_absent tests/test_profile_extractor.py::test_write_profile_and_log_updates_existing_profile tests/test_profile_extractor.py::test_write_profile_and_log_does_not_duplicate_heading -v
```
Expected: FAIL with `ImportError: cannot import name '_write_profile_and_log'`

- [ ] **Step 7: Implement `_write_profile_and_log`**

Append to `finances/backend/profile_extractor.py` (after `load_user_profile`):

```python
def _write_profile_and_log(new_profile: str, log_entry: str, notes_file: Path = _NOTES_FILE) -> None:
    today = date_type.today().isoformat()
    content = notes_file.read_text() if notes_file.exists() else ""
    profile_block = f"{_PROFILE_HEADING}\n_Last updated: {today}_\n\n{new_profile}\n"
    log_line = f"- **{today}**: {log_entry}"

    if _PROFILE_HEADING in content:
        start = content.find(_PROFILE_HEADING)
        next_sep = content.find("\n---", start)
        if next_sep == -1:
            content = content[:start] + profile_block
        else:
            content = content[:start] + profile_block + content[next_sep:]
    else:
        content = content.rstrip() + f"\n\n---\n\n{profile_block}"

    if _LOG_HEADING in content:
        log_start = content.find(_LOG_HEADING)
        next_sep = content.find("\n---", log_start + len(_LOG_HEADING))
        if next_sep == -1:
            content = content.rstrip() + f"\n{log_line}\n"
        else:
            content = content[:next_sep].rstrip() + f"\n{log_line}" + content[next_sep:]
    else:
        content = content.rstrip() + f"\n\n---\n\n{_LOG_HEADING}\n\n{log_line}\n"

    notes_file.write_text(content)
```

- [ ] **Step 8: Run all profile_extractor tests — expect PASS**

```bash
cd finances
pytest tests/test_profile_extractor.py -v
```
Expected: 6 PASS

- [ ] **Step 9: Commit**

```bash
git add finances/backend/profile_extractor.py finances/tests/test_profile_extractor.py
git commit -m "feat: add profile_extractor with load and write utilities"
```

---

### Task 2: `_call_claude_extract()` and `extract_and_update_profile()`

**Files:**
- Modify: `finances/backend/profile_extractor.py`
- Modify: `finances/tests/test_profile_extractor.py`

- [ ] **Step 1: Write failing tests**

Append to `finances/tests/test_profile_extractor.py`:

```python
@pytest.mark.asyncio
async def test_extract_and_update_profile_writes_on_update(tmp_path):
    from backend.profile_extractor import extract_and_update_profile
    f = tmp_path / "notes.md"
    f.write_text("# Notes\n")
    mock_result = {
        "update": True,
        "profile": "- Tracks expenses regularly",
        "log_entry": "Mentioned dining budget",
    }
    with patch("backend.profile_extractor._call_claude_extract", return_value=mock_result):
        await extract_and_update_profile("I spent $20 on lunch", "Saved! $20 at Chipotle.", f)
    content = f.read_text()
    assert "Tracks expenses regularly" in content
    assert "Mentioned dining budget" in content


@pytest.mark.asyncio
async def test_extract_and_update_profile_no_write_on_no_update(tmp_path):
    from backend.profile_extractor import extract_and_update_profile
    f = tmp_path / "notes.md"
    f.write_text("# Notes\n")
    with patch("backend.profile_extractor._call_claude_extract", return_value={"update": False}):
        await extract_and_update_profile("hello", "Hi there!", f)
    content = f.read_text()
    assert "## Current Profile" not in content


@pytest.mark.asyncio
async def test_extract_and_update_profile_swallows_exceptions(tmp_path):
    from backend.profile_extractor import extract_and_update_profile
    f = tmp_path / "notes.md"
    f.write_text("# Notes\n")
    with patch("backend.profile_extractor._call_claude_extract", side_effect=Exception("API down")):
        await extract_and_update_profile("hello", "Hi!", f)  # must not raise
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd finances
pytest tests/test_profile_extractor.py::test_extract_and_update_profile_writes_on_update tests/test_profile_extractor.py::test_extract_and_update_profile_no_write_on_no_update tests/test_profile_extractor.py::test_extract_and_update_profile_swallows_exceptions -v
```
Expected: FAIL with `ImportError: cannot import name 'extract_and_update_profile'` (and `_call_claude_extract`)

- [ ] **Step 3: Implement `_call_claude_extract` and `extract_and_update_profile`**

Append to `finances/backend/profile_extractor.py` (after `_write_profile_and_log`):

```python
def _call_claude_extract(exchange: str, current_profile: str) -> dict:
    prompt = (
        "You are a financial behavior analyst. Read the following conversation exchange "
        "and the current user profile, then decide if there is new financial signal worth recording.\n\n"
        f"Current profile:\n{current_profile if current_profile else '(empty — no profile yet)'}\n\n"
        f"Exchange:\n{exchange}\n\n"
        "Return JSON only. No explanation. Either:\n"
        '  {"update": false}\n'
        "if there is no new financial signal (e.g. balance queries, small talk, patterns already captured), or:\n"
        '  {"update": true, "profile": "<full rewritten profile as bullet points>", "log_entry": "<one-line observation>"}\n'
        "if a new behavioral pattern, goal, habit, or financial fact emerges.\n\n"
        "Profile bullet points should describe patterns and tendencies. "
        "Refine existing bullets rather than duplicating them."
    )
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.content[0].text)


async def extract_and_update_profile(
    user_message: str, assistant_reply: str, notes_file: Path = _NOTES_FILE
) -> None:
    try:
        current_profile = load_user_profile(notes_file)
        exchange = f"User: {user_message}\nAssistant: {assistant_reply}"
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _call_claude_extract, exchange, current_profile)
        if result.get("update") and result.get("profile") and result.get("log_entry"):
            _write_profile_and_log(result["profile"], result["log_entry"], notes_file)
    except Exception as e:
        logger.warning(f"Profile extraction failed: {e}")
```

- [ ] **Step 4: Run all profile_extractor tests — expect PASS**

```bash
cd finances
pytest tests/test_profile_extractor.py -v
```
Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add finances/backend/profile_extractor.py finances/tests/test_profile_extractor.py
git commit -m "feat: add async extract_and_update_profile with Claude Haiku extraction"
```

---

### Task 3: Wire into `chat.py`

**Files:**
- Modify: `finances/backend/chat.py:1-15` (imports), `finances/backend/chat.py:277` (profile in system), `finances/backend/chat.py:291` (fire task)
- Modify: `finances/tests/test_chat.py`

- [ ] **Step 1: Write failing tests**

Append to `finances/tests/test_chat.py`:

```python
def test_chat_includes_profile_in_system_prompt(client):
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"), \
         patch("backend.chat.load_user_profile", return_value="- Saves regularly"), \
         patch("backend.chat.asyncio.create_task"):
        _mock_claude(mock_cls, "OK")
        resp = client.post("/api/chat", data={"message": "hello", "history": "[]"})
    assert resp.status_code == 200
    call_kwargs = mock_cls.return_value.messages.create.call_args
    assert "Saves regularly" in call_kwargs.kwargs["system"]


def test_chat_fires_extraction_task(client):
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"), \
         patch("backend.chat.load_user_profile", return_value=""), \
         patch("backend.chat.asyncio.create_task") as mock_task:
        _mock_claude(mock_cls, "OK")
        client.post("/api/chat", data={"message": "hello", "history": "[]"})
    assert mock_task.called
```

- [ ] **Step 2: Run new tests — expect FAIL**

```bash
cd finances
pytest tests/test_chat.py::test_chat_includes_profile_in_system_prompt tests/test_chat.py::test_chat_fires_extraction_task -v
```
Expected: FAIL with `cannot import name 'load_user_profile' from 'backend.chat'` (or similar)

- [ ] **Step 3: Add imports to `chat.py`**

In `finances/backend/chat.py`, add two imports at the top alongside the existing stdlib imports (after `import base64`):

```python
import asyncio
```

And alongside the backend imports (after `from backend.anthropic_logger import log_usage`):

```python
from backend.profile_extractor import extract_and_update_profile, load_user_profile
```

- [ ] **Step 4: Prepend profile to system prompt**

In `finances/backend/chat.py`, after line 277 (`system += f"\n\n{result}"`):

```python
    profile = load_user_profile()
    if profile:
        system += f"\n\nUser financial profile (behavioral patterns observed over time):\n{profile}"
```

- [ ] **Step 5: Fire extraction task after reply**

In `finances/backend/chat.py`, after line 291 (`reply = response.content[0].text`):

```python
    asyncio.create_task(extract_and_update_profile(message, reply))
```

- [ ] **Step 6: Run all tests — expect full suite PASS**

```bash
cd finances
pytest tests/ -v
```
Expected: all tests PASS (previously passing tests unchanged, 2 new PASS)

- [ ] **Step 7: Commit**

```bash
git add finances/backend/chat.py finances/tests/test_chat.py
git commit -m "feat: wire financial profile extractor into chat endpoint"
```
