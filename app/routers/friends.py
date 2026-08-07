from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import Friendship, Goal, HabitLog, User, UserAchievement
from ..services import compute_streak

router = APIRouter(prefix="/api/friends", tags=["friends"])

# Порядок «крутости» ачивок — для выбора топ-ачивки друга
ACH_ORDER = ["friend1", "triple", "water7", "read7", "sport7", "steps10",
             "d1", "d3", "d7", "d21", "d30", "d90", "d365"]

def _started_dt(g: Goal) -> datetime:
    if g.started_at_ts:
        return datetime.fromtimestamp(g.started_at_ts)
    if g.started_at:
        return g.started_at
    return datetime.combine(g.start_date, datetime.min.time())

@router.get("")
async def friends(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    friend_ids = (await db.execute(
        select(Friendship.friend_id).where(
            Friendship.user_id == user.id,
            Friendship.status == "accepted")
    )).scalars().all()

    out = []
    for fid in friend_ids:
        fr = (await db.execute(select(User).where(User.id == fid))).scalar_one_or_none()
        if not fr:
            continue

        # Лучшая цель друга (максимум дней без срыва)
        goals = (await db.execute(
            select(Goal).where(Goal.user_id == fid, Goal.active.is_(True))
        )).scalars().all()
        days = max([max((datetime.now() - _started_dt(g)).days, 0) for g in goals], default=0)

        # Лучшая серия привычек за последние 40 дней
        since = date.today() - timedelta(days=40)
        logs = (await db.execute(
            select(HabitLog).where(HabitLog.user_id == fid, HabitLog.date >= since)
        )).scalars().all()
        by_habit: dict[str, set[date]] = {}
        for r in logs:
            by_habit.setdefault(r.habit, set()).add(r.date)
        best_streak = max([compute_streak(d, date.today()) for d in by_habit.values()], default=0)

        # Ачивки
        achs = list((await db.execute(
            select(UserAchievement.achievement_id).where(UserAchievement.user_id == fid)
        )).scalars().all())
        top_ach = None
        for a in ACH_ORDER:
            if a in achs:
                top_ach = a

        out.append({
            "name": fr.first_name,
            "days": days,
            "best_streak": best_streak,
            "ach_count": len(achs),
            "top_ach": top_ach,
        })
    return out
