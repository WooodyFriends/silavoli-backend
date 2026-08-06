from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..models import User
from ..schemas import AuthIn, AuthOut
from ..security import AuthError, issue_jwt, validate_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/session", response_model=AuthOut)
async def session(body: AuthIn, db: AsyncSession = Depends(get_db)):
    try:
        tg_user = validate_init_data(body.init_data)
    except AuthError as e:
        raise HTTPException(403, str(e))
    user = (await db.execute(select(User).where(User.tg_id == tg_user["id"]))).scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_user["id"],
                    username=tg_user.get("username"),
                    first_name=tg_user.get("first_name", "Боец"),
                    photo_url=(tg_user.get("photo") or {}).get("small_url"))
        db.add(user)
    else:
        user.first_name = tg_user.get("first_name", user.first_name)
        user.username = tg_user.get("username", user.username)
    await db.commit()
    await db.refresh(user)
    return AuthOut(token=issue_jwt(user.tg_id), name=user.first_name)
