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
            await check_premium_expirations()
        except Exception as e:
            print("[notify] error:", e)
            traceback.print_exc()
        await asyncio.sleep(300)

async def run_notifications():
    now_utc = datetime.now(timezone.utc)
    print(f"[notify] check at {now_utc.strftime('%H:%M:%S')} UTC")
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        print(f"[notify] found {len(users)} users")
        for u in users:
            enabled = bool(u.notify_enabled) if u.notify_enabled is not None else True
            if not enabled:
                continue
            tz = int(u.tz_offset) if u.tz_offset is not None else 3
            local = now_utc + timedelta(hours=tz)
            nh = int(u.notify_hour) if u.notify_hour is not None else 20
            nm = int(u.notify_minute) if u.notify_minute is not None else 0
            print(f"[notify] user {u.tg_id}: local={local.strftime('%H:%M')}, target={nh}:{nm:02d}")

            if local.hour != nh:
                continue
            diff = local.minute - nm
            if diff < 0 or diff >= 5:
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

async def check_premium_expirations():
    """Проверяем подписки, которые скоро истекают, и отправляем предупреждения."""
    now_utc = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            if not u.premium_until:
                continue
            
            # Вычисляем локальную дату пользователя
            tz = int(u.tz_offset) if u.tz_offset is not None else 3
            local_now = now_utc + timedelta(hours=tz)
            local_date = local_now.date()
            
            # Дата окончания подписки
            expires_date = u.premium_until.date()
            days_left = (expires_date - local_date).days
            
            # Отправляем предупреждения за 3 дня, 1 день и в день окончания
            if days_left in [3, 1, 0]:
                # Не отправляем одно и то же предупреждение дважды в один день
                if u.last_premium_warn_date == local_date:
                    continue
                
                kb = None
                if settings.mini_app_url:
                    kb = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="💎 Продлить подписку",
                                             web_app=WebAppInfo(url=settings.mini_app_url))]])
                
                if days_left == 3:
                    text = ("⏰ " + u.first_name + ", через 3 дня заканчивается Premium-подписка. "
                            "Продли, чтобы не потерять доступ к ИИ-компаньону и другим фичам 💎")
                elif days_left == 1:
                    text = ("⏰ " + u.first_name + ", завтра заканчивается Premium-подписка. "
                            "Не забудь продлить — мы рядом 24/7 💪")
                else:  # days_left == 0
                    text = ("💎 " + u.first_name + ", сегодня заканчивается Premium-подписка. "
                            "Спасибо, что был с нами! Продли, чтобы продолжить путь без ограничений.")
                
                u.last_premium_warn_date = local_date
                await db.commit()
                
                try:
                    await bot.send_message(u.tg_id, text, reply_markup=kb)
                    print(f"[premium] ⏰ WARNING sent to {u.tg_id} (expires in {days_left} days)")
                except Exception as e:
                    print("[premium] send fail:", e)
