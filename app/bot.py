from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo
from sqlalchemy import select
from .config import settings
from .db import SessionLocal
from .models import PendingRef

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
        "Каждый день без зависимости — победа.",
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
                await message.answer("🤝 Ты по приглашению друга — вы в одной команде!")
        except ValueError:
            pass
    await _welcome(message)

@router.message(CommandStart())
async def start(message: Message):
    await _welcome(message)

dp.include_router(router)
