import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select
from .bot import bot
from .config import settings
from .db import SessionLocal
from .models import HabitLog, User

async def notify_loop():
    print("[notify] LOOP STARTED")
    while True:
        try:
            await run_notifications()
        except Exception as e:
            print("[notify] error:", e)
            traceback.print_exc()
        await asyncio.sleep(300)  # проверка каждые 5 минут

async def run_notifications():
    now_utc = datetime.now(timezone.utc)
    print(f"[notify] check at {now_utc.strftime('%H:%M:%S')} UTC")
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        print(f"[notify] found {len(users)} users")
        for u in users:
            enabled = bool(u.notify_enabled) if u.notify_enabled is not None else True
            if not enabled:
                print(f"[notify] user {u.tg_id}: disabled, skip")
                continue
            tz = int(u.tz_offset) if u.tz_offset is not None else 3
            local = now_utc + timedelta(hours=tz)
            nh = int(u.notify_hour) if u.notify_hour is not None else 20
            print(f"[notify] user {u.tg_id}: local={local.strftime('%H:%M')}, notify_hour={nh}")
            if local.hour != nh:
                continue
            if u.last_notify_date == local.date():
                print(f"[notify] user {u.tg_id}: already notified today")
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
                print(f"[notify] ✅ SENT to {u.tg_id}")
            except Exception as e:
                print("[notify] send fail:", e)
