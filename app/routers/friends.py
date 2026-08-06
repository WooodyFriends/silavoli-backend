from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import Friendship, Goal, User

router = APIRouter(prefix="/api/friends", tags=["friends"])

@router.get("")
async def friends(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(User.first_name).join(Friendship, Friendship.friend_id == User.id)
        .where(Friendship.user_id == user.id, Friendship.status == "accepted")
    )).scalars().all()
    return [{"name": n, "days": None} for n in rows]
