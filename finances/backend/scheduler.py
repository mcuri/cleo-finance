import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _send_cc_reminder() -> None:
    from backend.config import get_settings
    from telegram import Bot

    settings = get_settings()
    if not settings.telegram_user_chat_id:
        logger.warning("TELEGRAM_USER_CHAT_ID not set — skipping CC reminder")
        return

    message = (
        "Hey! 👀 Credit card due in a few days — now's a good time to check "
        "your balance and make sure everything looks right. You've got this 💪"
    )

    async def _send():
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(chat_id=settings.telegram_user_chat_id, text=message)

    asyncio.run(_send())
    logger.info("CC reminder sent to chat %d", settings.telegram_user_chat_id)


def start() -> None:
    _scheduler.add_job(
        _send_cc_reminder,
        CronTrigger(day=27, hour=9, minute=0),
        id="cc_reminder",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — CC reminder fires on the 27th at 09:00")


def stop() -> None:
    _scheduler.shutdown(wait=False)
