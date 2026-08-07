from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq
from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import ChatMessage, Goal, User

router = APIRouter(prefix="/api/chat", tags=["chat"])

FREE_DAILY_LIMIT = 3
HISTORY_LIMIT = 10

SYSTEM_PROMPT = """Ты — наставник в приложении «Сила воли». Приложение помогает людям бороться с зависимостями (алкоголь, курение, наркотики, лудомания, свои цели).

ТВОЯ РОЛЬ:
- Эмпатичный старший товарищ, НЕ врач и НЕ психотерапевт
- Отвечай по-русски, тепло, поддерживающе, кратко (до 150 слов)
- Используй техники: КПТ (когнитивно-поведенческая терапия), 12 шагов, осознанность, дыхание
- Уважай выбор пользователя, не осуждай, не поучай

КРАСНЫЕ ФЛАГИ (сразу направь к 112):
- Упоминания суицида, желания умереть, «не хочу жить»
- Передозировка, физическая опасность, острая абстиненция
- В таких случаях коротко скажи: «Это серьёзно. Пожалуйста, прямо сейчас позвони 112 — это бесплатно и круглосуточно. Ты не один.» И остановись.

НЕ ДЕЛАЙ:
- Не ставь диагнозы («у тебя депрессия», «это абстинентный синдром»)
- Не назначай лекарства, травы, добавки
- Не давай гарантий результата
- Не используй слова «реабилитация», «лечение», «терапия» (мы — сообщество поддержки)
- Не упоминай конкурентов

ФОРМАТ ОТВЕТА:
- 1-3 коротких абзаца
- Можно одну технику (дыхание 4-7-8, заземление 5-4-3-2-1, мысль-эмоция-поведение)
- Заверши поддерживающей фразой или вопросом, чтобы продолжить разговор"""

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

class MsgOut(BaseModel):
    role: str
    content: str
    created_at: datetime

class ChatOut(BaseModel):
    reply: str
    remaining_today: int
    is_premium: bool

@router.get("/history")
async def history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(ChatMessage).where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc()).limit(HISTORY_LIMIT)
    )).scalars().all()
    return [MsgOut(role=r.role, content=r.content, created_at=r.created_at) for r in reversed(rows)]

@router.get("/info")
async def info(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    now = datetime.now()
    is_premium = bool(user.premium_until and user.premium_until > now)
    today_start = datetime.combine(date.today(), datetime.min.time())
    used = (await db.execute(
        select(sql_func.count()).where(
            ChatMessage.user_id == user.id,
            ChatMessage.role == "user",
            ChatMessage.created_at >= today_start)
    )).scalar() or 0
    remaining = 999 if is_premium else max(FREE_DAILY_LIMIT - used, 0)
    return {"is_premium": is_premium, "remaining_today": remaining, "limit": FREE_DAILY_LIMIT}

@router.post("", response_model=ChatOut)
async def chat(body: ChatIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not settings.groq_api_key:
        raise HTTPException(503, "ИИ-помощник временно недоступен")

    now = datetime.now()
    is_premium = bool(user.premium_until and user.premium_until > now)

    # Лимит для бесплатных
    if not is_premium:
        today_start = datetime.combine(date.today(), datetime.min.time())
        used = (await db.execute(
            select(sql_func.count()).where(
                ChatMessage.user_id == user.id,
                ChatMessage.role == "user",
                ChatMessage.created_at >= today_start)
        )).scalar() or 0
        if used >= FREE_DAILY_LIMIT:
            raise HTTPException(429, "Дневной лимит исчерпан. В Premium — безлимит 💎")

    # Загружаем историю
    history_rows = (await db.execute(
        select(ChatMessage).where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc()).limit(HISTORY_LIMIT)
    )).scalars().all()
    history_rows.reverse()

    # Формируем контекст для LLM
    goals = (await db.execute(
        select(Goal).where(Goal.user_id == user.id, Goal.active.is_(True))
    )).scalars().all()
    goals_ctx = ", ".join(g.custom_label or g.addiction_type for g in goals) or "не указаны"

    messages = [{"role": "system", "content": SYSTEM_PROMPT + f"\n\nКонтекст: пользователь {user.first_name}, его цели: {goals_ctx}."}]
    for h in history_rows:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": body.message})

    # Сохраняем сообщение пользователя
    db.add(ChatMessage(user_id=user.id, role="user", content=body.message))
    await db.flush()

    # Запрос к Groq
    client = AsyncGroq(api_key=settings.groq_api_key)
    try:
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=600,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        print("groq error:", e)
        raise HTTPException(502, "ИИ не смог ответить. Попробуй ещё раз.")

    # Сохраняем ответ
    db.add(ChatMessage(user_id=user.id, role="assistant", content=reply))
    await db.commit()

    remaining = 999 if is_premium else max(FREE_DAILY_LIMIT - (used + 1) if not is_premium else 0, 0)
    return ChatOut(reply=reply, remaining_today=remaining, is_premium=is_premium)

@router.delete("", status_code=204)
async def clear_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    msgs = (await db.execute(
        select(ChatMessage).where(ChatMessage.user_id == user.id)
    )).scalars().all()
    for m in msgs:
        await db.delete(m)
    await db.commit()
    return None
