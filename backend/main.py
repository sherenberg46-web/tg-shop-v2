"""
TG-Shop  |  FastAPI backend
Run: uvicorn backend.main:app --reload
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from aiogram.types import Update, MenuButtonWebApp, WebAppInfo
from bot.bot import dp, bot

from backend.database import init_db
from backend.routers import categories, products, cart, orders, favourites
from backend.routers import admin, banners, public_settings, collections
from backend.routers import parser

log = logging.getLogger(__name__)
UPLOAD_DIR = Path("static/uploads")

_polling_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _polling_task
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()

    # Start aiogram polling as a background task
    if settings.BOT_TOKEN:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🎮 Открыть магазин",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )
        )
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start", description="🏠 Главное меню"),
            BotCommand(command="help",  description="❓ Помощь"),
        ])
        log.info("Menu button and commands set")
        _polling_task = asyncio.create_task(dp.start_polling(bot))
        log.info("Telegram bot polling started")

    yield

    # Stop polling on shutdown
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    await bot.session.close()
    log.info("Telegram bot stopped")


app = FastAPI(
    title="TG-Shop API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,   # prevent 307 redirects that break the Vite proxy
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(categories.router, prefix="/api/v1")
app.include_router(products.router,   prefix="/api/v1")
app.include_router(cart.router,       prefix="/api/v1")
app.include_router(orders.router,     prefix="/api/v1")
app.include_router(favourites.router, prefix="/api/v1")
app.include_router(banners.router,          prefix="/api/v1")
app.include_router(collections.router,      prefix="/api/v1")
app.include_router(public_settings.router,  prefix="/api/v1")
app.include_router(admin.router,            prefix="/api/v1")
app.include_router(parser.router,     prefix="/api/v1")

# Serve uploaded product images
app.mount("/static", StaticFiles(directory="static", html=False), name="static")

@app.post("/webhook")
async def webhook(request: Request):
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
@app.get("/health")
async def health():
    return {"status": "ok"}
