import asyncio
from datetime import datetime, timedelta, timezone
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select
from .bot import bot
from .config import settings
from .db import SessionLocal
from .models import HabitLog, User

async def notify_loop():
    while True:
        try:
            await run_notifications()
        except Exception as e:
            print("notify error:", e)
        await asyncio.sleep(300)  # проверка каждые 5 минут

async def run_notifications():
    now_utc = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            if not u.notify_enabled:
                continue
            local = now_utc + timedelta(hours=(u.tz_offset or 3))
            if local.hour != (u.notify_hour or 20):
                continue
            if u.last_notify_date == local.date():
                continue
            logged = (await db.execute(
                select(HabitLog).where(HabitLog.user_id == u.id,
                                       HabitLog.date == local.date())
            )).scalars().first()
            u.last_notify_date = local.date()
            await db.commit()

            kb = None
            if settings.mini_app_url:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="💪 Открыть «Силу воли»",
                                         web_app=WebAppInfo(url=settings.mini_app_url))]])
            if logged:
                text = ("🎉 Привет, " + u.first_name + "! Ты уже отметил привычки сегодня — "
                        "ещё один день в копилку. Гордимся тобой!")
            else:
                text = ("🌙 " + u.first_name + ", как прошёл день? Загляни в «Силу воли» "
                        "и отметь привычки — одна минута заботы о себе.")
            try:
                await bot.send_message(u.tg_id, text, reply_markup=kb)
            except Exception as e:
                print("send fail:", e)
