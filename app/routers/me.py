from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import Goal, HabitLog, User, UserAchievement
from ..schemas import GoalIn, GoalOut, MeOut
from ..services import achievements_for, compute_streak

router = APIRouter(prefix="/api/me", tags=["me"])

@router.get("", response_model=MeOut)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    goal = (await db.execute(
        select(Goal).where(Goal.user_id == user.id, Goal.active.is_(True))
        .order_by(Goal.id.desc()))).scalars().first()

    days_clean = max((date.today() - goal.start_date).days, 0) if goal else 0

    since = date.today() - timedelta(days=40)
    rows = (await db.execute(
        select(HabitLog).where(HabitLog.user_id == user.id, HabitLog.date >= since)
    )).scalars().all()
    by_habit: dict[str, set[date]] = {}
    for r in rows:
        by_habit.setdefault(r.habit, set()).add(r.date)
    streaks = {h: compute_streak(by_habit.get(h, set()), date.today())
               for h in ("steps", "sport", "read")}
    all_today = all(date.today() in by_habit.get(h, set()) for h in streaks)

    earned = achievements_for(days_clean, streaks, all_today)
    existing = {a.achievement_id for a in (await db.execute(
        select(UserAchievement).where(UserAchievement.user_id == user.id))).scalars()}
    new_ids = [a for a in earned if a not in existing]
    for aid in new_ids:
        db.add(UserAchievement(user_id=user.id, achievement_id=aid))
    if new_ids:
        await db.commit()

    return MeOut(name=user.first_name, days_clean=days_clean, goal=goal,
                 streaks=streaks, achievements=sorted(earned))

@router.post("/goal", response_model=GoalOut, status_code=201)
async def set_goal(body: GoalIn, user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)):
    for g in (await db.execute(
            select(Goal).where(Goal.user_id == user.id, Goal.active.is_(True)))).scalars():
        g.active = False
    goal = Goal(user_id=user.id, addiction_type=body.addiction_type,
                custom_label=body.custom_label, start_date=body.start_date)
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal
