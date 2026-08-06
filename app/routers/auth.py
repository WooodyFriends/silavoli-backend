from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..models import Friendship, PendingRef, User
from ..schemas import AuthIn, AuthOut
from ..security import AuthError, issue_jwt, validate_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/session", response_model=AuthOut)
async def session(body: AuthIn, db: AsyncSession = Depends(get_db)):
    try:
        tg_user = validate_init_data(body.init_data)
    except AuthError as e:
        raise HTTPException(403, str(e))

    # 1. Ищем или создаём пользователя
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

    # 2. Новый механизм: start_param из Mini App
    referrer_tg_id = None
    if body.start_param and body.start_param.startswith("ref_"):
        try:
            referrer_tg_id = int(body.start_param[4:])
        except ValueError:
            pass

    # Фоллбек на старый механизм (через бота)
    if referrer_tg_id is None:
        ref = (await db.execute(
            select(PendingRef).where(PendingRef.tg_id == tg_user["id"])
        )).scalar_one_or_none()
        if ref and ref.referrer_id != user.tg_id:
            referrer_tg_id = ref.referrer_id
            await db.delete(ref)

    # 3. Создаём дружбу, если есть реферер
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

    await db.commit()
    await db.refresh(user)
    return AuthOut(token=issue_jwt(user.tg_id),
                   name=user.first_name, user_id=user.tg_id)
