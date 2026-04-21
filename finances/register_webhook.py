import asyncio
from telegram import Bot
from backend.config import get_settings


async def main():
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    url = f"{settings.app_url}/webhook"
    await bot.set_webhook(url=url, secret_token=settings.telegram_webhook_secret)
    info = await bot.get_webhook_info()
    print(f"Webhook set: {info.url}")


asyncio.run(main())
