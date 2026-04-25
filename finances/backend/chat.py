import json
import logging
from datetime import date as date_type
from typing import List

import anthropic
import backend.chat as _self
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.anthropic_logger import log_usage
from backend.claude_parser import parse_expense_text
from backend.config import get_settings
from backend.models import Transaction, TransactionCreate
from backend.sheets import SheetsClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

_MODEL = "claude-haiku-4-5-20251001"
_SYSTEM = (
    "You are Cleo, a personal finance assistant. "
    "You have access to the user's complete transaction history provided below. "
    "Answer questions concisely and specifically using the data. "
    "If expenses were just saved, acknowledge them first before answering any question. "
    "Use dollar amounts and dates from the data. Be brief — 2-4 sentences max unless detail is needed."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=get_settings().google_sheets_id)


def _get_sheets_client():
    return _self.get_sheets_client()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request_body: ChatRequest,
    sheets: SheetsClient = Depends(_get_sheets_client),
):
    # 1. Parse and save any expenses embedded in the message
    saved: List[Transaction] = []
    skipped_count = 0
    for parsed in parse_expense_text(request_body.message):
        expense_date = parsed.date or date_type.today()
        if sheets.find_duplicate(expense_date, parsed.amount, parsed.merchant):
            skipped_count += 1
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

    # 2. Fetch all transactions (after saving, so new ones are included)
    transactions = sheets.get_all_transactions()
    tx_json = json.dumps([
        {"date": str(t.date), "amount": t.amount, "merchant": t.merchant,
         "category": t.category, "type": t.type}
        for t in transactions
    ])

    # 3. Build system prompt with transaction context and save summary
    system = _SYSTEM + f"\n\nTransaction data: {tx_json}"
    if saved:
        summary = ", ".join(f"${t.amount:.2f} at {t.merchant} [{t.category}] on {t.date}" for t in saved)
        system += f"\n\nJust saved {len(saved)} expense(s): {summary}."
    if skipped_count:
        system += f" Skipped {skipped_count} duplicate(s)."

    # 4. Build message list from history + new message
    messages = [{"role": m.role, "content": m.content} for m in request_body.history[-20:]]
    messages.append({"role": "user", "content": request_body.message})

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
