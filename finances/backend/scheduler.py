import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _send_telegram(message: str) -> None:
    from backend.config import get_settings
    from telegram import Bot

    settings = get_settings()
    if not settings.telegram_user_chat_id:
        logger.warning("TELEGRAM_USER_CHAT_ID not set — skipping reminder")
        return

    async def _send():
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(chat_id=settings.telegram_user_chat_id, text=message)

    asyncio.run(_send())


def _send_cc_reminder() -> None:
    _send_telegram(
        "Hey! 👀 Credit card due in a few days — now's a good time to check "
        "your balance and make sure everything looks right. You've got this 💪"
    )
    logger.info("CC reminder sent")


def _send_rent_reminder() -> None:
    _send_telegram(
        "Rent's due today 🏠 — don't let it slip! Once it's paid, drop it in the app and we're all good."
    )
    logger.info("Rent reminder sent")


def start() -> None:
    _scheduler.add_job(
        _send_cc_reminder,
        CronTrigger(day=27, hour=9, minute=0),
        id="cc_reminder",
        replace_existing=True,
    )
    _scheduler.add_job(
        _send_rent_reminder,
        CronTrigger(day=1, hour=9, minute=0),
        id="rent_reminder",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — CC reminder on 27th, rent reminder on 1st, both at 09:00")


def stop() -> None:
    _scheduler.shutdown(wait=False)
