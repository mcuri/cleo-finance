import asyncio
import hmac
import json
import logging
from datetime import date as date_type
from typing import List, Optional, Tuple

import anthropic
from fastapi import APIRouter, Header, HTTPException, Request

from backend.anthropic_logger import log_usage
from backend.chat import _SYSTEM, _is_credit_card_bill, _is_payslip
from backend.claude_parser import parse_expense_text, parse_pdf_statement, parse_receipt_image
from backend.config import get_settings
from backend.models import ParsedExpense, Transaction, TransactionCreate
from backend.profile_extractor import extract_and_update_profile, load_user_profile
from backend.sheets import SheetsClient

router = APIRouter(tags=["telegram"])
logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


def _get_bot():
    from telegram import Bot
    return Bot(token=get_settings().telegram_bot_token)


def _verify_secret(token: Optional[str]) -> bool:
    if token is None:
        return False
    return hmac.compare_digest(token, get_settings().telegram_webhook_secret)


def _save_expenses(
    parsed_list: List[ParsedExpense],
    sheets: SheetsClient,
) -> Tuple[List[Transaction], int]:
    saved: List[Transaction] = []
    skipped = 0
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
                source="telegram",
            )
            sheets.append_transaction(t)
            saved.append(t)
    return saved, skipped


def _build_result(saved: List[Transaction], skipped: int) -> str:
    if saved:
        summary = ", ".join(
            f"${t.amount:.2f} at {t.merchant} [{t.category}] on {t.date}" for t in saved
        )
        result = f"[BACKEND RESULT] Saved {len(saved)} expense(s): {summary}."
        if skipped:
            result += f" Skipped {skipped} duplicate(s)."
        return result
    if skipped:
        return f"[BACKEND RESULT] All {skipped} expense(s) were duplicates — already in your history."
    return "[BACKEND RESULT] 0 expenses saved — message format not recognized by the expense parser."


def _build_system(sheets: SheetsClient, result: str) -> str:
    transactions = sheets.get_all_transactions()
    tx_json = json.dumps([
        {"date": str(t.date), "amount": t.amount, "merchant": t.merchant,
         "category": t.category, "type": t.type}
        for t in transactions
    ])
    system = _SYSTEM + f"\n\nTransaction data: {tx_json}\n\n{result}"
    profile = load_user_profile()
    if profile:
        system += f"\n\nUser financial profile (behavioral patterns observed over time):\n{profile}"
    return system


def _call_claude(system: str, user_text: str) -> str:
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    log_usage(response, "telegram")
    return response.content[0].text


async def _handle_text(chat_id: int, text: str) -> None:
    sheets = SheetsClient(spreadsheet_id=get_settings().google_sheets_id)
    saved, skipped = _save_expenses(parse_expense_text(text), sheets)
    result = _build_result(saved, skipped)
    system = _build_system(sheets, result)
    reply = _call_claude(system, text)
    bot = _get_bot()
    await bot.send_message(chat_id=chat_id, text=reply)
    asyncio.create_task(extract_and_update_profile(text, reply))


async def _handle_photo(chat_id: int, file_id: str) -> None:
    bot = _get_bot()
    tg_file = await bot.get_file(file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    sheets = SheetsClient(spreadsheet_id=get_settings().google_sheets_id)
    saved, skipped = _save_expenses(parse_receipt_image(image_bytes, "image/jpeg"), sheets)
    result = _build_result(saved, skipped)
    system = _build_system(sheets, result)
    reply = _call_claude(system, "[User sent a receipt image]")
    await bot.send_message(chat_id=chat_id, text=reply)
    asyncio.create_task(extract_and_update_profile("[receipt image]", reply))


async def _handle_document(chat_id: int, file_id: str, file_name: str) -> None:
    from backend.credit_card_parser import (
        categorize_transactions,
        dedup_and_save_credit_card_transactions,
        parse_credit_card_bill_pdf,
    )
    from backend.drive import DriveClient
    from backend.payslip_parser import parse_payslip

    bot = _get_bot()
    tg_file = await bot.get_file(file_id)
    file_bytes = bytes(await tg_file.download_as_bytearray())
    sheets = SheetsClient(spreadsheet_id=get_settings().google_sheets_id)
    saved: List[Transaction] = []
    skipped = 0
    result = ""

    if _is_credit_card_bill(file_bytes):
        try:
            cc_txs = parse_credit_card_bill_pdf(file_bytes)
            await categorize_transactions(cc_txs)
            saved, skipped = dedup_and_save_credit_card_transactions(cc_txs, sheets)
            result = f"[BACKEND RESULT] Saved {len(saved)} credit card transaction(s)."
            if skipped:
                result += f" Skipped {skipped} duplicate(s)."
        except Exception as e:
            logger.warning(f"Error parsing CC bill: {e}")
            result = f"[BACKEND RESULT] Failed to parse credit card statement: {e}"
        try:
            DriveClient().upload_pdf(
                file_bytes, file_name, "Credit Card Bills",
                date_type.today().strftime("%Y-%m"),
            )
        except Exception as e:
            logger.warning(f"Drive upload failed for CC bill: {e}")
    elif _is_payslip(file_bytes):
        parsed_payslips = parse_payslip(file_bytes)
        payslip_summaries = []
        for p in parsed_payslips:
            if sheets.find_duplicate_payslip(p.company, p.check_date):
                skipped += 1
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
                f"{p.company} (Net: ${p.net_pay:,.2f}, Date: {p.check_date})"
            )
        result = (
            f"[BACKEND RESULT] Saved {len(parsed_payslips)} payslip(s) and "
            f"{len(saved)} income transaction(s): " + "; ".join(payslip_summaries) + "."
        )
        try:
            DriveClient().upload_pdf(
                file_bytes, file_name, "Payslips",
                parsed_payslips[0].check_date.strftime("%Y-%m") if parsed_payslips
                else date_type.today().strftime("%Y-%m"),
            )
        except Exception as e:
            logger.warning(f"Drive upload failed for payslip: {e}")
    else:
        saved, skipped = _save_expenses(parse_pdf_statement(file_bytes), sheets)
        result = _build_result(saved, skipped)

    system = _build_system(sheets, result)
    reply = _call_claude(system, f"[User sent a PDF: {file_name}]")
    await bot.send_message(chat_id=chat_id, text=reply)
    asyncio.create_task(extract_and_update_profile(f"[PDF: {file_name}]", reply))


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    if not _verify_secret(x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id: int = message["chat"]["id"]

    if "text" in message:
        asyncio.create_task(_handle_text(chat_id, message["text"]))
    elif "photo" in message:
        largest = sorted(message["photo"], key=lambda p: p.get("file_size", 0))[-1]
        asyncio.create_task(_handle_photo(chat_id, largest["file_id"]))
    elif "document" in message:
        doc = message["document"]
        if doc.get("mime_type") == "application/pdf":
            asyncio.create_task(
                _handle_document(chat_id, doc["file_id"], doc.get("file_name", "document.pdf"))
            )

    return {"ok": True}
