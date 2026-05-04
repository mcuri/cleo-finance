import json
import logging
import re
from datetime import date as date_type
from pathlib import Path
from typing import List, Optional, Tuple

import anthropic

from backend.config import get_settings
from backend.models import ParsedExpense, Transaction, TransactionCreate
from backend.sheets import SheetsClient

logger = logging.getLogger(__name__)


class CreditCardTransaction:
    """Parsed credit card transaction."""

    def __init__(
        self,
        tran_date: date_type,
        post_date: date_type,
        merchant: str,
        amount: float,
        location: str = "",
        raw_description: str = "",
        category: str = "Uncategorized",
    ):
        self.tran_date = tran_date
        self.post_date = post_date
        self.merchant = merchant
        self.amount = amount
        self.location = location
        self.raw_description = raw_description
        self.category = category

    def __repr__(self):
        return f"CreditCardTransaction({self.tran_date}, ${self.amount:.2f}, {self.merchant}, {self.category})"


def _load_category_keywords() -> dict:
    """Load keyword mappings for category inference."""
    keywords_path = Path(__file__).parent / "category_keywords.json"
    try:
        with open(keywords_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Category keywords file not found at {keywords_path}")
        return {}


def _save_category_keywords(keywords: dict) -> None:
    """Save updated keyword mappings."""
    keywords_path = Path(__file__).parent / "category_keywords.json"
    with open(keywords_path, "w") as f:
        json.dump(keywords, f, indent=2)


def _infer_category_from_keywords(
    description: str, keywords: dict
) -> Optional[str]:
    """Try to infer category from keyword mapping using description."""
    description_upper = description.upper()
    for category, keywords_list in keywords.items():
        for keyword in keywords_list:
            if keyword.upper() in description_upper:
                return category
    return None


async def _infer_category_from_claude(description: str) -> str:
    """Ask Claude to infer the transaction category from description."""
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    prompt = (
        f'Infer a single transaction category for this transaction description. '
        f'Respond with ONLY the category name (no explanation).\n\n'
        f'Description: {description}\n\n'
        f'Categories: Travel, Transport, Groceries, Restaurants, Fitness, Shopping, Entertainment, '
        f'Utilities, Training, Laundry, Medical, Subscriptions, Other'
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}],
    )
    category = response.content[0].text.strip()
    return category if category else "Other"


async def infer_category(description: str) -> str:
    """
    Infer category for a transaction description using keywords, then Claude fallback.
    Updates the keyword mapping if Claude is used.
    """
    keywords = _load_category_keywords()

    # Try keyword matching first
    inferred = _infer_category_from_keywords(description, keywords)
    if inferred:
        return inferred

    # Fallback to Claude
    category = await _infer_category_from_claude(description)

    # Add new keyword to mapping for future use
    if category in keywords:
        # Use first word of cleaned merchant name as keyword
        cleaned_desc = _clean_merchant_name(description)
        merchant_keyword = cleaned_desc.split()[0].upper() if cleaned_desc else ""
        if merchant_keyword and merchant_keyword not in keywords[category]:
            keywords[category].append(merchant_keyword)
            _save_category_keywords(keywords)
            logger.info(
                f"Added '{merchant_keyword}' to {category} keywords in mapping"
            )

    return category


def _clean_merchant_name(description: str) -> str:
    """Extract clean merchant name from raw transaction description."""
    # Remove alphanumeric reference numbers at end (like 24610436Y03R4Apvw)
    desc = re.sub(r"\s+[A-Z0-9]{10,}\s*$", "", description, flags=re.IGNORECASE)

    # Remove location patterns at the end (CITY STATE/COUNTRY)
    desc = re.sub(r"\s+([A-Z]{2,}(?:\s+[A-Z]{2,})?)\s+(CA|TX|NY|WA|MX|US)\s*$", "", desc)

    # Strip payment processor prefixes first (before asterisk removal, so merchant words are preserved)
    desc = re.sub(r"^SQ\s\*", "", desc)
    desc = re.sub(r"^EB\s\*", "", desc)
    desc = re.sub(r"^PY\s\*", "", desc)
    desc = re.sub(r"^MERPAGO\*", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"^CLIP MX\*", "", desc, flags=re.IGNORECASE)

    # Remove order/session IDs after asterisk — only if the code contains digits
    # (e.g. PRIME*ME7FM04U3 → PRIME, but SQ *MISSION and MERPAGO*LOSTULIPANES are handled above)
    desc = re.sub(r"\*(?=[A-Z0-9]*\d)[A-Z0-9]+", "", desc, flags=re.IGNORECASE)

    # Remove store numbers (#XXXX)
    desc = re.sub(r"#\d+", "", desc)

    # Remove URL paths but keep domain+TLD as merchant name
    # e.g. APPLE.COM/BILL → APPLE.COM, Amzn.com/bill → Amzn.com, WWW.NETFLIX.COM → NETFLIX.COM
    desc = re.sub(r"(?:WWW\.)(\w+\.(?:com|net|org|io|co))(/\S*)?\s*", r"\1 ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"(\b\w+\.(?:com|net|org|io|co))(/\S*)?\s*", r"\1 ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"http\S+", "", desc, flags=re.IGNORECASE)

    # Remove phone numbers (XXX-XXX-XXXX, XXX-XXXX, (XXX) XXX-XXXX, etc)
    desc = re.sub(r"\d{3}-\d{3}-\d{4}", "", desc)
    desc = re.sub(r"\d{3}-\d{4}", "", desc)
    desc = re.sub(r"\(\d{3}\)\s*\d{3}-\d{4}", "", desc)

    # Remove long numeric sequences (reference numbers)
    desc = re.sub(r"\s*\d{10,}\s*", " ", desc)
    desc = re.sub(r"\s+\d{13,}\s+", " ", desc)

    # Remove trailing numeric-only words
    words = desc.split()
    while words and words[-1].isdigit():
        words.pop()
    desc = " ".join(words)

    # Second-pass: strip trailing state code left over after URL/phone removal
    # (e.g. "APPLE CA" after stripping "APPLE.COM/BILL 866-712-7753")
    # Only apply if it leaves a non-empty result
    _STATE_CODES = {"CA", "TX", "NY", "WA", "MX", "US", "OR", "AZ", "FL", "IL", "MA", "CO"}
    words = desc.split()
    if len(words) >= 2 and words[-1].upper() in _STATE_CODES:
        candidate = " ".join(words[:-1]).strip()
        if candidate:
            desc = candidate

    # Final whitespace cleanup + title case
    desc = " ".join(desc.split()).strip()
    result = desc.title()
    # Keep TLD lowercase (title() would capitalise ".Com" → ".com")
    result = re.sub(r"\.(Com|Net|Org|Io|Co)\b", lambda m: "." + m.group(1).lower(), result)
    return result


def _extract_location(description: str) -> str:
    """Extract location (city, state) from description."""
    # Try to extract city and state/country from end
    # Handle multi-word cities like "SAN FRANCISCO"
    match = re.search(r"([A-Z\s]+)\s+(CA|TX|NY|WA|MX|US)(?:\s|$)", description)
    if match:
        city = match.group(1).strip()
        state = match.group(2)
        return f"{city}, {state}"
    return ""


def _parse_date(date_str: str, year: int) -> date_type:
    """Parse MM/DD date string and add year."""
    month, day = map(int, date_str.split("/"))
    return date_type(year, month, day)


def _normalize_header(cell: str) -> str:
    value = str(cell or "").strip().lower()
    value = re.sub(r"[^a-z]+", " ", value).strip()
    if "tran" in value and "date" in value:
        return "tran_date"
    if "post" in value and "date" in value:
        return "post_date"
    if "description" in value or "merchant" in value:
        return "description"
    if "amount" in value or "transaction amount" in value:
        return "amount"
    if "reference" in value or "ref" in value:
        return "reference"
    return value.replace(" ", "_")


def _parse_transaction_amount(amount_str: str) -> Optional[float]:
    amount_str = amount_str.strip()
    if not amount_str:
        return None
    amount_str = amount_str.replace("$", "").replace(",", "")
    negative = False
    if amount_str.startswith("(") and amount_str.endswith(")"):
        negative = True
        amount_str = amount_str[1:-1]
    try:
        amount = float(amount_str)
        if negative:
            amount = abs(amount)
        return amount
    except ValueError:
        return None


_FOOTER_MARKERS = (
    "SEE REVERSE SIDE", "PLEASE DETACH", "BILLING RIGHTS",
    "IMPORTANT INFORMATION", "ACCOUNT NUMBER ENDING",
    "PAYMENT DUE DATE", "NEW BALANCE", "MINIMUM PAYMENT",
    "TRANSACTIONS (CONTINUED)", "TRAN POST REFERENCE",
    "PAGE 1 OF", "PAGE 2 OF", "PAGE 3 OF", "RETAIN UPPER",
)

# Amount pattern reused in both regexes
_AMOUNT_PAT = r"-?\$?\(?\$?\d{1,3}(?:,\d{3})*\.\d{2}\)?"
# Optional trailing reference number (alphanumeric, 10+ chars) before amount
_REF_PAT = r"(?:\s+[A-Z0-9]{10,})?"


def _parse_credit_card_text(text: str, statement_year: int) -> List[CreditCardTransaction]:
    """Parse credit card transaction rows from plain extracted PDF text."""
    transactions: List[CreditCardTransaction] = []
    current_tx: Optional[CreditCardTransaction] = None

    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue

        # Stop continuation accumulation at page footer / section headers
        upper = cleaned.upper()
        if any(m in upper for m in _FOOTER_MARKERS):
            current_tx = None
            continue

        # Lines with tran date + post date + description (+ optional ref) + amount
        match = re.match(
            rf"^(\d{{2}}/\d{{2}})\s+(\d{{2}}/\d{{2}})\s+(.+?){_REF_PAT}\s+({_AMOUNT_PAT})$",
            cleaned,
        )
        if match:
            tran_date_str, post_date_str, description, amount_str = match.groups()
            tran_date = _parse_date(tran_date_str, statement_year)
            post_date = _parse_date(post_date_str, statement_year)
            amount = _parse_transaction_amount(amount_str)
            if amount is None or amount <= 0:
                current_tx = None
                continue
            merchant = _clean_merchant_name(description)
            location = _extract_location(description)
            if merchant:
                current_tx = CreditCardTransaction(
                    tran_date=tran_date,
                    post_date=post_date,
                    merchant=merchant,
                    amount=amount,
                    location=location,
                    raw_description=description,
                )
                transactions.append(current_tx)
            else:
                current_tx = None
            continue

        # Lines with tran date only + description (+ optional ref) + amount
        match = re.match(
            rf"^(\d{{2}}/\d{{2}})\s+(.+?){_REF_PAT}\s+({_AMOUNT_PAT})$",
            cleaned,
        )
        if match:
            tran_date_str, description, amount_str = match.groups()
            tran_date = _parse_date(tran_date_str, statement_year)
            post_date = tran_date
            amount = _parse_transaction_amount(amount_str)
            if amount is None or amount <= 0:
                current_tx = None
                continue
            merchant = _clean_merchant_name(description)
            location = _extract_location(description)
            if merchant:
                current_tx = CreditCardTransaction(
                    tran_date=tran_date,
                    post_date=post_date,
                    merchant=merchant,
                    amount=amount,
                    location=location,
                    raw_description=description,
                )
                transactions.append(current_tx)
            else:
                current_tx = None
            continue

        # Append genuine continuation lines (e.g. wrapped merchant names)
        if current_tx and not re.match(r"^\d{2}/\d{2}", cleaned):
            current_tx.raw_description += " " + cleaned
            current_tx.merchant = _clean_merchant_name(current_tx.raw_description)
            current_tx.location = _extract_location(current_tx.raw_description)

    return transactions


def parse_credit_card_bill_pdf(
    file_bytes: bytes, statement_year: Optional[int] = None
) -> List[CreditCardTransaction]:
    """
    Extract transactions from Stanford FCU credit card PDF.

    Args:
        file_bytes: PDF file bytes
        statement_year: Year for transactions (extracted from PDF if not provided)

    Returns:
        List of CreditCardTransaction objects
    """
    try:
        import pdfplumber
        import io
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is required to parse credit card PDF statements. "
            "Install it from requirements.txt or run `pip install pdfplumber`."
        ) from exc

    transactions = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        if statement_year is None:
            for page in pdf.pages:
                text = page.extract_text() or ""
                date_match = re.search(
                    r"Statement Closing Date\s+(\d{2})/(\d{2})/(\d{4})", text, re.IGNORECASE
                )
                if date_match:
                    statement_year = int(date_match.group(3))
                    break

        if statement_year is None:
            statement_year = date_type.today().year

        for page in pdf.pages:
            tables = page.extract_tables() or []
            logger.debug("CC page %d: %d tables found", page.page_number, len(tables))
            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = None
                data_start_idx = None
                for idx, row in enumerate(table):
                    if row and any(
                        "tran" in str(cell or "").lower() and "date" in str(cell or "").lower()
                        for cell in row
                    ):
                        header = row
                        data_start_idx = idx + 1
                        break

                if not header or data_start_idx is None:
                    logger.debug("CC table on page %d: no tran-date header found, header row: %s", page.page_number, table[0] if table else [])
                    continue

                column_map = {}
                for idx, cell in enumerate(header):
                    column_map[_normalize_header(str(cell or ""))] = idx

                def cell_text(row, key):
                    idx = column_map.get(key)
                    if idx is None or idx >= len(row):
                        return ""
                    return str(row[idx] or "").strip()

                i = data_start_idx
                current_tx = None
                while i < len(table):
                    row = table[i]
                    if not row or not any(cell for cell in row if cell):
                        i += 1
                        continue

                    tran_date_str = cell_text(row, "tran_date") or str(row[0] or "").strip()
                    if not re.match(r"\d{2}/\d{2}", tran_date_str):
                        if current_tx and any(cell for cell in row if cell):
                            continuation = " ".join(str(cell or "").strip() for cell in row if cell)
                            upper = continuation.upper()
                            if any(m in upper for m in _FOOTER_MARKERS):
                                current_tx = None
                            else:
                                current_tx.raw_description += " " + continuation
                                current_tx.merchant = _clean_merchant_name(current_tx.raw_description)
                                current_tx.location = _extract_location(current_tx.raw_description)
                        i += 1
                        continue

                    post_date_str = cell_text(row, "post_date")
                    description = cell_text(row, "description")
                    amount_str = cell_text(row, "amount")

                    if not amount_str:
                        for cell in reversed(row):
                            text = str(cell or "").strip()
                            if re.search(r"-?\$?\(?\$?\d{1,3}(?:,\d{3})*\.\d{2}\)?$", text):
                                amount_str = text
                                break

                    try:
                        tran_date = _parse_date(tran_date_str, statement_year)
                        post_date = _parse_date(post_date_str, statement_year) if post_date_str else tran_date
                        amount = _parse_transaction_amount(amount_str) if amount_str else None
                        if amount is None or amount <= 0:
                            current_tx = None
                            i += 1
                            continue

                        if not description:
                            description = " ".join(
                                str(cell or "").strip() for idx, cell in enumerate(row) if idx not in {column_map.get("tran_date"), column_map.get("post_date"), column_map.get("amount")}
                            ).strip()

                        merchant = _clean_merchant_name(description)
                        location = _extract_location(description)
                        if merchant:
                            current_tx = CreditCardTransaction(
                                tran_date=tran_date,
                                post_date=post_date,
                                merchant=merchant,
                                amount=amount,
                                location=location,
                                raw_description=description,
                            )
                            transactions.append(current_tx)
                        else:
                            current_tx = None
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse row {i}: {row}, error: {e}")
                        current_tx = None

                    i += 1

        if not transactions:
            pages_text = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                pages_text.append(t)
            full_text = "\n".join(pages_text)
            logger.debug("CC text fallback, first 500 chars: %s", full_text[:500])
            transactions = _parse_credit_card_text(full_text, statement_year)

    logger.info(f"Parsed {len(transactions)} transactions from credit card PDF")
    return transactions


async def categorize_transactions(
    transactions: List[CreditCardTransaction],
) -> None:
    """
    Categorize transactions using keyword matching and Claude fallback.
    Updates transactions in-place using only the description column.
    """
    for tx in transactions:
        category = await infer_category(tx.raw_description)
        tx.category = category


def dedup_and_save_credit_card_transactions(
    transactions: List[CreditCardTransaction],
    sheets: SheetsClient,
) -> Tuple[List[Transaction], int]:
    """
    Deduplicate against existing transactions and save to Sheets.

    Args:
        transactions: Parsed credit card transactions
        sheets: SheetsClient instance

    Returns:
        (saved_transactions, skipped_count)
    """
    saved: List[Transaction] = []
    skipped = 0

    # Fetch existing transactions once
    existing = sheets.get_all_transactions()
    seen = {(t.date, t.amount, t.merchant.lower()) for t in existing}

    for cc_tx in transactions:
        key = (cc_tx.post_date, cc_tx.amount, cc_tx.merchant.lower())
        if key in seen:
            skipped += 1
            logger.info(f"Skipped duplicate: {cc_tx.merchant} ${cc_tx.amount}")
        else:
            seen.add(key)
            # Convert to Transaction model and save
            tx = Transaction.from_create(
                TransactionCreate(
                    date=cc_tx.post_date,
                    amount=cc_tx.amount,
                    merchant=cc_tx.merchant,
                    category=cc_tx.category,
                    type="expense",
                    notes=cc_tx.location,
                ),
                source="credit_card",
            )
            sheets.append_transaction(tx)
            saved.append(tx)
            logger.info(f"Saved: {cc_tx.merchant} ${cc_tx.amount} [{cc_tx.category}]")

    return saved, skipped
