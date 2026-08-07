import asyncio
import time
from datetime import datetime
from aiogram import Router
from aiogram.types import Message
from groq import AsyncGroq
from sqlalchemy import select
from .bot import bot
from .config import settings
from .db import SessionLocal
from .models import User

router = Router()

KEYWORDS = ["тяга", "срыв", "сорвался", "сорвалась", "накрыло", "хочу выпить",
            "хочу курить", "хочу закурить", "плохо", "трудно", "не могу",
            "помоги", "помогите", "держусь", "слабость"]

GROUP_SYSTEM_PROMPT = """Ты — наставник в закрытом чате поддержки «Сила воли». Здесь люди, которые борются с зависимостями.
Отвечай КОРОТКО (до 80 слов), тепло, по-русски. Обращайся по имени.
Ты в групповом чате: не читай нотации, поддерживай, предлагай ОДНУ конкретную технику.
Красные флаги (суицид, передоз, «не хочу жить») — сразу: «Это серьёзно. Позвони 112 — бесплатно и круглосуточно. Ты не один.» И остановись.
Не ставь диагнозы, не назначай лекарства, не используй слова «лечение» и «реабилитация»."""

_last_reply: dict[int, float] = {}
COOLDOWN_MENTION = 10
COOLDOWN_KEYWORD = 3600

async def send_premium_invite(tg_id: int):
    """Одноразовая ссылка в закрытую группу для премиум-пользователя."""
    if not settings.premium_group_id:
        print("[group] premium_group_id not set, skip invite")
        return
    try:
        link = await bot.create_chat_invite_link(
            chat_id=settings.premium_group_id, member_limit=1)
        await bot.send_message(
            tg_id,
            "💎 Premium активен! Держи разовую ссылку в закрытую группу «Силы воли»:\n\n"
            + link.invite_link +
            "\n\nСсылка одноразовая — никому не пересылай.")
        print(f"[group] invite sent to {tg_id}")
    except Exception as e:
        print("[group] invite fail:", e)

async def kick_user(tg_id: int):
    """Исключить из группы (с разбаном, чтобы мог вернуться по новой ссылке)."""
    if not settings.premium_group_id:
        return
    try:
        await bot.ban_chat_member(settings.premium_group_id, tg_id)
        await asyncio.sleep(1)
        await bot.unban_chat_member(settings.premium_group_id, tg_id)
        print(f"[group] kicked {tg_id}")
    except Exception as e:
        print("[group] kick fail:", e)

@router.message()
async def group_handler(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    # Лог для настройки: ловим id группы
    print(f"[group] chat id: {message.chat.id} from {message.from_user.id}: "
          f"{(message.text or '')[:40]}")
        if settings.premium_group_id != 0 and message.chat.id != settings.premium_group_id:
        return

    if message.from_user.is_bot:
        return

    text = message.text or message.caption or ""
    low = text.lower()

    async with SessionLocal() as db:
        u = (await db.execute(
            select(User).where(User.tg_id == message.from_user.id)
        )).scalar_one_or_none()
    now = datetime.now()
    is_premium = bool(u and u.premium_until and u.premium_until > now)

    # ===== МОДЕРАЦИЯ: ссылки от не-премиум =====
    if ("t.me/" in low or "http://" in low or "https://" in low) and not is_premium:
        try:
            await message.delete()
            await message.answer("🚫 Реклама и сторонние ссылки в чате запрещены.")
        except Exception as e:
            print("[group] mod fail:", e)
        return

    # ===== ИИ-ПОДДЕРЖКА =====
    mention = ("@" + settings.bot_username.lower()) in low
    reply_to_bot = bool(message.reply_to_message and message.reply_to_message.from_user
                        and message.reply_to_message.from_user.id == bot.id)
    distress = any(k in low for k in KEYWORDS)

    last = _last_reply.get(message.from_user.id, 0)
    if mention or reply_to_bot:
        if time.time() - last < COOLDOWN_MENTION:
            return
    elif distress:
        if time.time() - last < COOLDOWN_KEYWORD:
            return
    else:
        return  # не вмешиваемся в обычные разговоры

    _last_reply[message.from_user.id] = time.time()
    name = message.from_user.first_name or "друг"

    if not settings.groq_api_key:
        return
    client = AsyncGroq(api_key=settings.groq_api_key)
    try:
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": GROUP_SYSTEM_PROMPT},
                {"role": "user", "content": f"Сообщение из чата от {name}: {text}"}],
            temperature=0.7, max_tokens=300)
        reply = resp.choices[0].message.content.strip()
        await message.reply(reply)
        print(f"[group] ai replied to {message.from_user.id}")
    except Exception as e:
        print("[group] ai fail:", e)
