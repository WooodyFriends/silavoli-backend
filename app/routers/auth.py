from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..bot import bot
from ..db import get_db
from ..models import Friendship, PendingRef, User
from ..schemas import AuthIn, AuthOut
from ..security import AuthError, issue_jwt, validate_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])

def _extend_premium(user: User, days: int = 30):
    """Продлевает премиум на N дней от max(now, premium_until)."""
    now = datetime.now()
    base = user.premium_until if (user.premium_until and user.premium_until > now) else now
    user.premium_until = base + timedelta(days=days)


@router.post("/session", response_model=AuthOut)
async def session(body: AuthIn, db: AsyncSession = Depends(get_db)):
    try:
        tg_user = validate_init_data(body.init_data)
    except AuthError as e:
        raise HTTPException(403, str(e))

    user = (await db.execute(
        select(User).where(User.tg_id == tg_user["id"])
    )).scalar_one_or_none()

    if user is None:
        user = User(tg_id=tg_user["id"], username=tg_user.get("username"),
                    first_name=tg_user.get("first_name", "Боец"),
                    photo_url=(tg_user.get("photo") or {}).get("small_url"))
        db.add(user)
        await db.flush()
    else:
        user.first_name = tg_user.get("first_name", user.first_name)
        user.username = tg_user.get("username", user.username)

    # Приглашение: работаем и со start_param, и со старым PendingRef
    referrer_tg_id = None
    if body.start_param and body.start_param.startswith("ref_"):
        try:
            referrer_tg_id = int(body.start_param[4:])
        except ValueError:
            pass
    if referrer_tg_id is None:
        ref = (await db.execute(
            select(PendingRef).where(PendingRef.tg_id == tg_user["id"])
        )).scalar_one_or_none()
        if ref and ref.referrer_id != user.tg_id:
            referrer_tg_id = ref.referrer_id
            await db.delete(ref)

    # Создаём дружбу и даём бонус ОБОИМ
    bonus_given = False
    if referrer_tg_id and referrer_tg_id != user.tg_id:
        referrer_user = (await db.execute(
            select(User).where(User.tg_id == referrer_tg_id)
        )).scalar_one_or_none()
        if referrer_user:
            already = (await db.execute(
                select(Friendship).where(Friendship.user_id == user.id,
                                         Friendship.friend_id == referrer_user.id)
            )).scalar_one_or_none()
            if not already:
                # Дружба в обе стороны
                user.referred_by = referrer_user.tg_id
                db.add(Friendship(user_id=user.id, friend_id=referrer_user.id,
                                  status="accepted"))
                db.add(Friendship(user_id=referrer_user.id, friend_id=user.id,
                                  status="accepted"))
                # 🎁 БОНУС: +30 дней премиум обоим
                _extend_premium(user, 30)
                _extend_premium(referrer_user, 30)
                bonus_given = True

    await db.commit()
    await db.refresh(user)

    # Уведомления (не блокируем ответ, если упадёт)
    if bonus_given:
        try:
            await bot.send_message(user.tg_id,
                "🎁 Ты по приглашению друга — у вас обоих +30 дней Premium! "
                "Пользуйся: безлимит целей, ИИ-компаньон и всё остальное.")
            await bot.send_message(referrer_user.tg_id,
                "🎁 Друг пришёл по твоей ссылке! У вас обоих +30 дней Premium. "
                "Так держать 💪")
        except Exception as e:
            print("bonus notify fail:", e)

    return AuthOut(token=issue_jwt(user.tg_id),
                   name=user.first_name, user_id=user.tg_id)
