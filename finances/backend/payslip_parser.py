import base64
import json
from typing import List

import anthropic

from backend.anthropic_logger import log_usage
from backend.config import get_settings
from backend.models import ParsedPayslip

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You extract payslip summary data from PDF documents. "
    "Respond ONLY with a valid JSON array — no explanation, no markdown. "
    "Return an array even if the PDF contains only one payslip."
)

_SCHEMA = (
    '[{"company": "...", "pay_period_begin": "YYYY-MM-DD", "pay_period_end": "YYYY-MM-DD", '
    '"check_date": "YYYY-MM-DD", "gross_pay": 0.00, "pre_tax_deductions": 0.00, '
    '"employee_taxes": 0.00, "post_tax_deductions": 0.00, "net_pay": 0.00, '
    '"employee_401k": 0.00, "employer_401k_match": 0.00, "life_choice": 0.00}, ...]'
)


def parse_payslip(pdf_bytes: bytes) -> List[ParsedPayslip]:
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
                },
                {
                    "type": "text",
                    "text": (
                        f"Extract all current-period payslip summaries and return a JSON array matching: {_SCHEMA}\n\n"
                        "Use 0.0 for any field not present. "
                        "All dates must be YYYY-MM-DD. All amounts are numbers, not strings."
                    ),
                },
            ],
        }],
    )
    log_usage(response, "parse_payslip")
    return _parse_response(response.content[0].text)


def _parse_response(text: str) -> List[ParsedPayslip]:
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(cleaned)
        if isinstance(data, dict):
            data = [data]
        return [ParsedPayslip(**item) for item in data]
    except Exception:
        return []
