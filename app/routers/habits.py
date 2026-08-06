from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import HabitLog, User
from ..schemas import CheckIn, CheckOut
from ..services import compute_streak

router = APIRouter(prefix="/api/habits", tags=["habits"])

@router.post("/check", response_model=CheckOut)
async def check(body: CheckIn, user: User = Depends(get_current_user),
                db: AsyncSession = Depends(get_db)):
    d = body.check_date or date.today()
    if d > date.today():
        raise HTTPException(400, "future date")
    if (date.today() - d).days > 1:
        raise HTTPException(400, "only today or yesterday")
    try:
        db.add(HabitLog(user_id=user.id, habit=body.habit, date=d))
        await db.commit()
    except IntegrityError:
        await db.rollback()
    rows = await db.execute(
        select(HabitLog.date).where(HabitLog.user_id == user.id,
                                    HabitLog.habit == body.habit,
                                    HabitLog.date >= d - timedelta(days=40)))
    return CheckOut(ok=True, streak=compute_streak({r[0] for r in rows}, date.today()))
