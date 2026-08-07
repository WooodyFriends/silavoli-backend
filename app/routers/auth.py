from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..bot import bot
from ..db import get_db
from ..models import Friendship, PendingRef, User
from ..schemas import AuthIn, AuthOut
from ..security import AuthError, issue_jwt, validate_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])

# За этих по счёту друзей — месяц премиум обоим (один раз)
PREMIUM_MILESTONES = {3, 100}

def _extend_premium(user: User, days: int = 30):
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

    # Источник приглашения: start_param или старый PendingRef
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

    notify = None
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
                user.referred_by = referrer_user.tg_id
                db.add(Friendship(user_id=user.id, friend_id=referrer_user.id,
                                  status="accepted"))
                db.add(Friendship(user_id=referrer_user.id, friend_id=user.id,
                                  status="accepted"))
                await db.flush()  # чтобы счётчик учёл нового друга
                cnt = (await db.execute(
                    select(func.count()).where(
                        Friendship.user_id == referrer_user.id,
                        Friendship.status == "accepted")
                )).scalar() or 0

                if cnt in PREMIUM_MILESTONES:
                    # 🎁 МИЛЕСТОУН: месяц премиум обоим
                    _extend_premium(user, 30)
                    _extend_premium(referrer_user, 30)
                    notify = ("milestone", cnt)
                else:
                    notify = ("progress", cnt)

    await db.commit()
    await db.refresh(user)

    if notify:
        kind, cnt = notify
        try:
            if kind == "milestone":
                await bot.send_message(user.tg_id,
                    f"🎁 Ты стал другом №{cnt} в команде! Дарим тебе месяц Premium 💎")
                await bot.send_message(referrer_user.tg_id,
                    f"🎁 В команде {cnt} человека! Дарим вам обоим месяц Premium. "
                    "Ты настоящий наставник 💪")
            else:
                left = 3 - cnt if cnt < 3 else 100 - cnt
                await bot.send_message(referrer_user.tg_id,
                    f"🤝 Новый друг в команде! До подарка Premium осталось: {left}. "
                    "Продолжай звать своих 💪")
                await bot.send_message(user.tg_id,
                    "🤝 Добро пожаловать в команду! Зови своих — за 3-го друга "
                    "дарим месяц Premium 🎁")
        except Exception as e:
            print("bonus notify fail:", e)

    return AuthOut(token=issue_jwt(user.tg_id),
                   name=user.first_name, user_id=user.tg_id)
