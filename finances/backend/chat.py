import base64
import json
import logging
from datetime import date as date_type
from typing import List, Optional, Tuple

import anthropic
import backend.chat as _self
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.anthropic_logger import log_usage
from backend.claude_parser import parse_expense_text, parse_pdf_statement, parse_receipt_image
from backend.config import get_settings
from backend.models import ParsedExpense, Transaction, TransactionCreate
from backend.sheets import SheetsClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

_MODEL = "claude-haiku-4-5-20251001"
_SYSTEM = (
    "You are Cleo, a personal finance assistant backed by a real app.\n\n"
    "The system context below includes a [BACKEND RESULT] line. "
    "That line is machine-generated output from the backend — it is factual, not your belief. "
    "Report it to the user directly as fact. "
    "Never say 'I think', 'I believe', 'I cannot confirm', or hedge about whether saving worked. "
    "Never say 'I cannot save' or 'you need to save elsewhere' — saving is handled entirely by "
    "the backend before you respond.\n\n"
    "If [BACKEND RESULT] says expenses were saved: confirm them ('Saved X expenses: ...').\n"
    "If [BACKEND RESULT] says the format was not recognized: tell the user their message format "
    "wasn't understood by the parser and give examples that work "
    "(e.g. 'spent $12.50 at Trader Joe\\'s on Groceries', or attach a receipt image or PDF).\n\n"
    "Answer questions about transaction history using the data below. "
    "Be brief — 2-4 sentences unless detail is needed."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    reply: str


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=get_settings().google_sheets_id)


def _get_sheets_client():
    return _self.get_sheets_client()


def _save_expenses(
    parsed_list: List[ParsedExpense],
    sheets: SheetsClient,
) -> Tuple[List[Transaction], int]:
    saved: List[Transaction] = []
    skipped = 0
    for parsed in parsed_list:
        expense_date = parsed.date or date_type.today()
        if sheets.find_duplicate(expense_date, parsed.amount, parsed.merchant):
            skipped += 1
        else:
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

    if file:
        file_bytes = await file.read()
        b64 = base64.standard_b64encode(file_bytes).decode()
        ct = file.content_type or ""
        if ct.startswith("image/"):
            saved, skipped_count = _save_expenses(parse_receipt_image(file_bytes, ct), sheets)
            file_block = {"type": "image", "source": {"type": "base64", "media_type": ct, "data": b64}}
        elif ct == "application/pdf":
            saved, skipped_count = _save_expenses(parse_pdf_statement(file_bytes), sheets)
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
    system = _SYSTEM + f"\n\nTransaction data: {tx_json}"
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
        result = "[BACKEND RESULT] 0 expenses saved — message format not recognized by the expense parser."
    system += f"\n\n{result}"

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

    # 6. Log usage
    log_usage(response, "chat")

    return ChatResponse(reply=reply)
