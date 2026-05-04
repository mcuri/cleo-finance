import asyncio
import json
import logging

import anthropic

from backend.config import get_settings

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


def _get_sheets():
    from backend.sheets import SheetsClient
    return SheetsClient(spreadsheet_id=get_settings().google_sheets_id)


def load_user_profile() -> str:
    try:
        return _get_sheets().get_profile()
    except Exception as e:
        logger.warning("Could not load profile from Sheets: %s", e)
        return ""


def _write_profile_and_log(new_profile: str, log_entry: str) -> None:
    try:
        _get_sheets().update_profile(new_profile, log_entry)
    except Exception as e:
        logger.warning("Could not write profile to Sheets: %s", e)


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
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.content:
        logger.warning("Profile extractor: empty response from Claude")
        return {"update": False}
    raw = response.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        normalized = raw.replace("True", "true").replace("False", "false")
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            logger.warning("Profile extractor: unexpected Claude response: %s", raw)
            return {"update": False}


async def extract_and_update_profile(user_message: str, assistant_reply: str) -> None:
    try:
        current_profile = load_user_profile()
        exchange = f"[USER]\n{user_message}\n\n[ASSISTANT]\n{assistant_reply}"
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _call_claude_extract, exchange, current_profile)
        if result.get("update") and result.get("profile") and result.get("log_entry"):
            await loop.run_in_executor(
                None, _write_profile_and_log, result["profile"], result["log_entry"]
            )
    except Exception as e:
        logger.warning("Profile extraction failed: %s", e)
