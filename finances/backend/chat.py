import asyncio
import base64
import json
import logging
from datetime import date as date_type
from pathlib import Path
from typing import List, Optional, Tuple

import anthropic
import backend.chat as _self
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.anthropic_logger import log_usage
from backend.claude_parser import parse_expense_text, parse_pdf_statement, parse_receipt_image
from backend.profile_extractor import extract_and_update_profile, load_user_profile
from backend.config import get_settings
from backend.credit_card_parser import (
    categorize_transactions,
    dedup_and_save_credit_card_transactions,
    parse_credit_card_bill_pdf,
)
from backend.models import ParsedExpense, Transaction, TransactionCreate
from backend.payslip_parser import parse_payslip
from backend.drive import DriveClient
from backend.sheets import SheetsClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

_MODEL = "claude-haiku-4-5-20251001"


def _load_cleo_persona() -> str:
    """Load Cleo persona from markdown file."""
    persona_path = Path(__file__).parent / "cleo_persona.md"
    with open(persona_path, "r") as f:
        content = f.read()
    # Remove the markdown heading and strip whitespace
    lines = content.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


_SYSTEM = _load_cleo_persona()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    reply: str


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=get_settings().google_sheets_id)


def _get_sheets_client():
    return _self.get_sheets_client()


def _is_credit_card_bill(file_bytes: bytes) -> bool:
    """Detect if PDF is a credit card statement by checking for known markers."""
    try:
        import pdfplumber
        import io
    except ImportError:
        logger.warning("pdfplumber is not installed; skipping credit card bill detection")
        return False

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lower = text.lower()
                # Check for credit card / statement markers
                if any(
                    marker in lower
                    for marker in [
                        "stanford fcu",
                        "credit union",
                        "statement closing date",
                        "new balance",
                        "minimum payment",
                        "previous balance",
                        "available credit",
                        "amount due",
                        "tran date",
                    ]
                ):
                    return True
    except Exception as e:
        logger.warning(f"Error detecting credit card bill: {e}")
    return False


def _is_payslip(file_bytes: bytes) -> bool:
    """Detect if PDF is a payslip by matching 3+ of the known field markers."""
    try:
        import pdfplumber
        import io
    except ImportError:
        return False

    markers = ["net pay", "gross pay", "pay period", "pre tax deductions", "check date"]
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if pdf.pages:
                text = (pdf.pages[0].extract_text() or "").lower()
                found = sum(1 for m in markers if m in text)
                return found >= 3
    except Exception as e:
        logger.warning(f"Error detecting payslip: {e}")
    return False


def _save_expenses(
    parsed_list: List[ParsedExpense],
    sheets: SheetsClient,
) -> Tuple[List[Transaction], int]:
    saved: List[Transaction] = []
    skipped = 0
    # Fetch once; also track newly saved keys so within-batch duplicates are caught
    existing = sheets.get_all_transactions()
    seen = {(t.date, t.amount, t.merchant.lower()) for t in existing}
    for parsed in parsed_list:
        expense_date = parsed.date or date_type.today()
        key = (expense_date, parsed.amount, parsed.merchant.lower())
        if key in seen:
            skipped += 1
        else:
            seen.add(key)
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
    result = None

    if file:
        file_bytes = await file.read()
        b64 = base64.standard_b64encode(file_bytes).decode()
        ct = file.content_type or ""
        if ct.startswith("image/"):
            saved, skipped_count = _save_expenses(parse_receipt_image(file_bytes, ct), sheets)
            file_block = {"type": "image", "source": {"type": "base64", "media_type": ct, "data": b64}}
        elif ct == "application/pdf":
            # Check if this is a credit card statement
            if _is_credit_card_bill(file_bytes):
                logger.info("Detected credit card statement, using specialized parser")
                try:
                    cc_transactions = parse_credit_card_bill_pdf(file_bytes)
                    logger.info(f"Parsed {len(cc_transactions)} transactions from credit card bill")
                    await categorize_transactions(cc_transactions)
                    logger.info("Categorized transactions")
                    saved, skipped_count = dedup_and_save_credit_card_transactions(
                        cc_transactions, sheets
                    )
                    logger.info(f"Saved {len(saved)} credit card transactions, skipped {skipped_count}")
                except Exception as e:
                    logger.error(f"Error parsing credit card bill: {e}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to parse credit card statement: {str(e)}",
                    )
                try:
                    DriveClient().upload_pdf(
                        file_bytes,
                        file.filename or "cc_bill.pdf",
                        "Credit Card Bills",
                        date_type.today().strftime("%Y-%m"),
                    )
                except Exception as e:
                    logger.warning(f"Drive upload failed for CC bill: {e}")
            elif _is_payslip(file_bytes):
                parsed_payslips = parse_payslip(file_bytes)
                if not parsed_payslips:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not extract payslip data from this PDF.",
                    )
                payslip_summaries = []
                for p in parsed_payslips:
                    if sheets.find_duplicate_payslip(p.company, p.check_date):
                        skipped_count += 1
                        continue
                    sheets.append_payslip(p)
                    income_tx = Transaction.from_create(
                        TransactionCreate(
                            date=p.check_date,
                            amount=p.net_pay,
                            merchant=p.company,
                            category="Income",
                            type="income",
                            notes=f"Pay period: {p.pay_period_begin} - {p.pay_period_end}",
                        ),
                        source="payslip",
                    )
                    sheets.append_transaction(income_tx)
                    saved.append(income_tx)
                    payslip_summaries.append(
                        f"{p.company} (Gross: ${p.gross_pay:,.2f}, Net: ${p.net_pay:,.2f}, Date: {p.check_date})"
                    )
                result = (
                    f"[BACKEND RESULT] Saved {len(parsed_payslips)} payslip(s) to Payslips sheet "
                    f"and {len(saved)} income transaction(s): "
                    + "; ".join(payslip_summaries)
                    + "."
                )
                try:
                    DriveClient().upload_pdf(
                        file_bytes,
                        file.filename or "payslip.pdf",
                        "Payslips",
                        parsed_payslips[0].check_date.strftime("%Y-%m"),
                    )
                except Exception as e:
                    logger.warning(f"Drive upload failed for payslip: {e}")
            else:
                # Generic PDF statement parser
                saved, skipped_count = _save_expenses(
                    parse_pdf_statement(file_bytes), sheets
                )
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
    system = _SYSTEM + f"\n\nToday's date: {date_type.today().isoformat()}\n\nTransaction data: {tx_json}"
    if result is None:
        if saved:
            summary = ", ".join(
                f"${t.amount:.2f} at {t.merchant} [{t.category}] on {t.date}" for t in saved
            )
            result = f"[BACKEND RESULT] Saved {len(saved)} expense(s): {summary}."
            if skipped_count:
                result += f" Skipped {skipped_count} duplicate(s)."
        elif skipped_count:
            result = f"[BACKEND RESULT] All {skipped_count} expense(s) were duplicates — already in your history."
        else:
            result = ""
    if result:
        system += f"\n\n{result}"
    profile = load_user_profile()
    if profile:
        system += f"\n\nUser financial profile (behavioral patterns observed over time):\n{profile}"

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
    asyncio.create_task(extract_and_update_profile(message, reply))

    # 6. Log usage
    log_usage(response, "chat")

    return ChatResponse(reply=reply)
