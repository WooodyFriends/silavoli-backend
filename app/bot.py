from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo
from .config import settings

bot = Bot(settings.bot_token)
dp = Dispatcher()
router = Router()

@router.message(CommandStart())
async def start(message: Message):
    text = (f"Привет, {message.from_user.first_name}! Я бот «Силы воли» 💪\n"
            "Каждый день без зависимости — победа. Открывай приложение и отмечай прогресс.")
    if settings.mini_app_url:
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[
            KeyboardButton(text="💪 Открыть «Силу воли»",
                           web_app=WebAppInfo(url=settings.mini_app_url))]])
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text)

dp.include_router(router)
