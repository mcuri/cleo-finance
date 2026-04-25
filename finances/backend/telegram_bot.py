import asyncio
import hmac
from datetime import date
from typing import Optional

from fastapi import APIRouter, Request, Header, HTTPException

from backend.config import get_settings
from backend.claude_parser import parse_expense_text, parse_receipt_image
from backend.models import Transaction, TransactionCreate
from backend.sheets import SheetsClient

router = APIRouter(tags=["telegram"])


def _get_bot():
    from telegram import Bot
    return Bot(token=get_settings().telegram_bot_token)


def _verify_secret(token: Optional[str]) -> bool:
    if token is None:
        return False
    return hmac.compare_digest(token, get_settings().telegram_webhook_secret)


async def _save_and_reply(chat_id: int, parsed, source_label: str) -> None:
    sheets = SheetsClient(spreadsheet_id=get_settings().google_sheets_id)
    expense_date = parsed.date or date.today()
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
    bot = _get_bot()
    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"Saved ({source_label}): ${t.amount:.2f} at {t.merchant} "
            f"[{t.category}] on {t.date}"
        ),
    )


async def _handle_text(chat_id: int, text: str) -> None:
    parsed = parse_expense_text(text)
    if not parsed or parsed.confidence < 0.5:
        bot = _get_bot()
        await bot.send_message(
            chat_id=chat_id,
            text="Couldn't extract an expense from that. Try something like: 'lunch at Itaim for 45 reais' or 'paid 120 for Uber'",
        )
        return
    await _save_and_reply(chat_id, parsed, "text")


async def _handle_photo(chat_id: int, file_id: str) -> None:
    bot = _get_bot()
    tg_file = await bot.get_file(file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    parsed = parse_receipt_image(image_bytes, "image/jpeg")
    if not parsed or parsed.confidence < 0.5:
        await bot.send_message(
            chat_id=chat_id,
            text="Couldn't read that receipt. Send the details as text instead.",
        )
        return
    await _save_and_reply(chat_id, parsed, "receipt")


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

    return {"ok": True}
