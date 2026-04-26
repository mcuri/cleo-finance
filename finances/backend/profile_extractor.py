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
    nl = content.find("\n", start)
    if nl == -1:
        return ""
    section_start = nl + 1
    if content[section_start:].startswith("_Last updated"):
        nl2 = content.find("\n", section_start)
        if nl2 == -1:
            return ""
        section_start = nl2 + 1
    end = len(content)
    for marker in ["\n---", "\n## "]:
        pos = content.find(marker, section_start)
        if pos != -1 and pos < end:
            end = pos
    return content[section_start:end].strip()


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
