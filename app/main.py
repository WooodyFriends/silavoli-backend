import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram.types import Update
from .config import settings
from .db import Base, engine
from .bot import bot, dp
from .notifications import notify_loop
from .routers import auth, friends, habits, me, premium

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if settings.public_url:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.set_webhook(
                f"{settings.public_url}/bot/webhook",
                allowed_updates=["message", "pre_checkout_query"]
            )
            logger.info("webhook set with allowed_updates")
        except Exception as e:
            logger.warning("webhook: %s", e)
    try:
        bot_me = await bot.get_me()
        if not settings.bot_username:
            settings.bot_username = bot_me.username
    except Exception as e:
        logger.warning("get_me: %s", e)
    logger.info("🌙 starting notification loop")
    task = asyncio.create_task(notify_loop())
    yield
    task.cancel()

app = FastAPI(title="Сила воли API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list,
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "sila-voli"}

@app.post("/bot/webhook")
async def tg_webhook(request: Request):
    data = await request.json()
    if "pre_checkout_query" in data:
        print("[webhook] pre_checkout_query:", data)
    elif "message" in data and "successful_payment" in data.get("message", {}):
        print("[webhook] successful_payment:", data)
    await dp.feed_update(bot, Update.model_validate(data))
    return {"ok": True}

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(habits.router)
app.include_router(friends.router)
app.include_router(premium.router)
