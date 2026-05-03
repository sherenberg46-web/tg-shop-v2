"""
TG-Shop Telegram Bot — sales funnel with AI consultant.

Run: python bot/bot.py
"""
import asyncio
import logging
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

load_dotenv()

# Try Redis storage if REDIS_URL is set, fall back to memory
def _make_storage():
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
            return RedisStorage.from_url(redis_url)
        except Exception as e:
            logging.warning("Redis storage unavailable (%s), using MemoryStorage", e)
    return MemoryStorage()


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    # fallback to backend config
    try:
        from backend.config import settings
        BOT_TOKEN = settings.BOT_TOKEN or ""
    except Exception:
        pass

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=_make_storage())

# Register routers
from bot.handlers.start import router as start_router
dp.include_router(start_router)


async def main() -> None:
    log.info("Starting GAME STORE bot with AI consultant…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
