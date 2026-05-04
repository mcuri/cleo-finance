import io
import logging
import re
from datetime import date as date_type
from typing import List, Optional

from backend.models import ParsedExpense

logger = logging.getLogger(__name__)

_SERVICE_CATEGORIES = {
    "rent service fee": "Rent",
    "rent": "Rent",
    "pest control": "Utilities",
    "water heating": "Utilities",
    "sewer": "Utilities",
    "trash": "Utilities",
    "water": "Utilities",
    "electric": "Utilities",
    "gas": "Utilities",
    "internet": "Utilities",
    "cable": "Subscriptions",
}

_SKIP_PATTERNS = ("charges due", "total", "grand total", "prior balance")

# Pattern: SERVICE_NAME  MM/DD/YYYY - MM/DD/YYYY  $X,XXX.XX
_LINE_RE = re.compile(
    r"^(.+?)\s+"
    r"(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})"
    r"\s+(\$[\d,]+\.\d{2})$"
)


def _parse_date(s: str) -> Optional[date_type]:
    try:
        m, d, y = map(int, s.strip().split("/"))
        return date_type(y, m, d)
    except (ValueError, AttributeError):
        return None


def _parse_amount(s: str) -> Optional[float]:
    try:
        val = float(s.strip().replace("$", "").replace(",", ""))
        return val if val > 0 else None
    except (ValueError, AttributeError):
        return None


def _infer_category(service: str) -> str:
    lower = service.lower().strip()
    for key, cat in _SERVICE_CATEGORIES.items():
        if key in lower:
            return cat
    return "Utilities"


def parse_rental_bill_pdf(file_bytes: bytes) -> List[ParsedExpense]:
    """Parse a Conservice-style rental + utility bill into one ParsedExpense per line item."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed; cannot parse rental bill")
        return []

    expenses: List[ParsedExpense] = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            # Only page 1 has the charge data
            text = pdf.pages[0].extract_text() if pdf.pages else ""
            if not text:
                return []

            # Extract due date
            due_date: Optional[date_type] = None
            m = re.search(r"Due Date[:\s]+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
            if m:
                due_date = _parse_date(m.group(1))

            for line in text.splitlines():
                line = line.strip()
                match = _LINE_RE.match(line)
                if not match:
                    continue
                service, period_str, amount_str = match.groups()
                service = service.strip()

                if any(p in service.lower() for p in _SKIP_PATTERNS):
                    continue

                amount = _parse_amount(amount_str)
                if amount is None:
                    continue

                # Use due date for the transaction; period as notes
                period_str = period_str.strip()
                expenses.append(ParsedExpense(
                    date=due_date,
                    amount=amount,
                    merchant=service,
                    category=_infer_category(service),
                    notes=f"Period: {period_str}",
                ))

    except Exception as e:
        logger.warning("Error parsing rental bill: %s", e)

    logger.info("Parsed %d line items from rental bill PDF", len(expenses))
    return expenses
