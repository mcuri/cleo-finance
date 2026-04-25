import json
import base64
from datetime import date
from typing import List, Optional

import anthropic

from backend.config import get_settings
from backend.models import ParsedExpense

_client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

_MODEL = "claude-haiku-4-5-20251001"

_CATEGORIES = [
    "Utilities", "Groceries", "Restaurants", "Transport",
    "Entertainment", "Health", "Shopping", "Travel", "Income", "Other",
]

_TEXT_SYSTEM = (
    "You extract expense details from natural-language messages. "
    "Respond ONLY with a valid JSON array — no explanation, no markdown. "
    "Each element must be a JSON object. Return an array even for a single expense."
)

_RECEIPT_SYSTEM = (
    "You read receipt images and extract expense details. "
    "Respond ONLY with a valid JSON array — no explanation, no markdown. "
    "Each element must be a JSON object. Return an array even for a single expense."
)

_JSON_SCHEMA = (
    '[{{"amount": <number>, "merchant": "<string>", "category": "<one of: {cats}>", '
    '"date": "<YYYY-MM-DD or null>", "notes": "<string or null>", "confidence": <0.0-1.0>}}, ...]'
)


def parse_expense_text(text: str) -> List[ParsedExpense]:
    schema = _JSON_SCHEMA.format(cats=", ".join(_CATEGORIES))
    prompt = (
        f"Extract all expenses from this message and return a JSON array matching: {schema}\n\n"
        f"Today is {date.today().isoformat()}. Use today for the date if not stated.\n\n"
        f"Message: {text}"
    )
    response = _client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_TEXT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_response(response.content[0].text)


def parse_receipt_image(image_bytes: bytes, media_type: str) -> List[ParsedExpense]:
    schema = _JSON_SCHEMA.format(cats=", ".join(_CATEGORIES))
    b64 = base64.standard_b64encode(image_bytes).decode()
    response = _client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_RECEIPT_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": f"Extract all expenses and return a JSON array matching: {schema}"},
            ],
        }],
    )
    return _parse_response(response.content[0].text)


def _parse_response(text: str) -> List[ParsedExpense]:
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(cleaned)
        if isinstance(data, dict):
            data = [data]
        return [ParsedExpense(**item) for item in data if item.get("confidence", 1.0) >= 0.5]
    except Exception:
        return []
