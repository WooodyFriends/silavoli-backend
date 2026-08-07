import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from aiogram import F
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy import select
from datetime import datetime, timedelta
from .config import settings
from .db import Base, engine, SessionLocal
from .bot import bot, dp
from .notifications import notify_loop
from .routers import auth, friends, habits, me, premium, chat
from .models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    print("[pay] pre_checkout_query from", query.from_user.id, "payload:", query.invoice_payload)
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def on_payment(message: Message):
    print("[pay] successful_payment received, payload:", message.successful_payment.invoice_payload)
    async with SessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.tg_id == message.from_user.id))).scalar_one_or_none()
        if user:
            now = datetime.now()
            base = user.premium_until if (user.premium_until and user.premium_until > now) else now
            user.premium_until = base + timedelta(days=30)
            await db.commit()
            print("[pay] premium_until updated to", user.premium_until)
    await message.answer("💎 Подписка активна! Спасибо, что веришь в «Силу воли».\n"
                         "Премиум-функции уже открыты.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("webhook deleted, switching to polling")
    except Exception as e:
        logger.warning("delete_webhook: %s", e)
    try:
        bot_me = await bot.get_me()
        if not settings.bot_username:
            settings.bot_username = bot_me.username
    except Exception as e:
        logger.warning("get_me: %s", e)
    logger.info("🌙 starting background tasks")
    t1 = asyncio.create_task(notify_loop())
    t2 = asyncio.create_task(dp.start_polling(bot))
    yield
    t1.cancel()
    t2.cancel()

app = FastAPI(title="Сила воли API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list,
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "sila-voli"}

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(habits.router)
app.include_router(friends.router)
app.include_router(premium.router)
app.include_router(chat.router)
