from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (KeyboardButton, Message, PreCheckoutQuery,
                           ReplyKeyboardMarkup, WebAppInfo)
from sqlalchemy import select
from .config import settings
from .db import SessionLocal
from .models import PendingRef, User

bot = Bot(settings.bot_token)
dp = Dispatcher()
router = Router()

async def _welcome(message: Message):
    kb = None
    if settings.mini_app_url:
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[
            KeyboardButton(text="💪 Открыть «Силу воли»",
                           web_app=WebAppInfo(url=settings.mini_app_url))]])
    await message.answer(
        f"Привет, {message.from_user.first_name}! Я бот «Силы воли» 💪\n"
        "Каждый день без зависимости — победа. Открывай приложение и отмечай прогресс.",
        reply_markup=kb)

@router.message(CommandStart(deep_link=True))
async def start_ref(message: Message, command: CommandObject):
    arg = command.args or ""
    if arg.startswith("ref_"):
        try:
            referrer = int(arg[4:])
            if referrer != message.from_user.id:
                async with SessionLocal() as db:
                    row = (await db.execute(
                        select(PendingRef).where(PendingRef.tg_id == message.from_user.id))
                    ).scalar_one_or_none()
                    if row:
                        row.referrer_id = referrer
                    else:
                        db.add(PendingRef(tg_id=message.from_user.id, referrer_id=referrer))
                    await db.commit()
                await message.answer("🤝 Ты пришёл по приглашению друга — теперь вы в одной команде!")
        except ValueError:
            pass
    await _welcome(message)

@router.message(CommandStart())
async def start(message: Message):
    await _welcome(message)

# ===== ПЛАТЕЖИ TELEGRAM STARS =====

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    print("[pay] pre_checkout_query from", query.from_user.id)
    await query.answer(ok=True)
    print("[pay] pre_checkout answered OK")

@router.message(F.successful_payment)
async def on_payment(message: Message):
    print("[pay] successful_payment received")
    async with SessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.tg_id == message.from_user.id))).scalar_one_or_none()
        if user:
            now = datetime.now()
            base = user.premium_until if (user.premium_until and user.premium_until > now) else now
            user.premium_until = base + timedelta(days=30)
            await db.commit()
    await message.answer("💎 Подписка активна! Спасибо, что веришь в «Силу воли». "
                         "Премиум-функции уже открыты.")

dp.include_router(router)
