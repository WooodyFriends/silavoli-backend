from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import Friendship, Goal, HabitLog, User, UserAchievement
from ..schemas import GoalIn, GoalOut, MeOut, NameIn, RestartIn, StatsOut
from ..services import achievements_for, compute_streak

router = APIRouter(prefix="/api/me", tags=["me"])

def _started_at(sd: date, st: str | None) -> datetime:
    now = datetime.now()
    if st:
        h, m = map(int, st.split(":"))
        dt = datetime.combine(sd, time(h, m))
    elif sd == date.today():
        dt = now
    else:
        dt = datetime.combine(sd, time.min)
    return dt if dt < now else now

def _started(g: Goal) -> datetime:
    return g.started_at or datetime.combine(g.start_date, time.min)

def _goal_out(g: Goal) -> GoalOut:
    return GoalOut(id=g.id, addiction_type=g.addiction_type, custom_label=g.custom_label,
                   start_date=g.start_date, started_at=_started(g),
                   days_clean=max((datetime.now() - _started(g)).days, 0))

@router.get("", response_model=MeOut)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    goals = (await db.execute(
        select(Goal).where(Goal.user_id == user.id, Goal.active.is_(True))
        .order_by(Goal.id))).scalars().all()
    goals_out = [_goal_out(g) for g in goals]

    since = date.today() - timedelta(days=40)
    rows = (await db.execute(
        select(HabitLog).where(HabitLog.user_id == user.id, HabitLog.date >= since)
    )).scalars().all()
    by_habit: dict[str, set[date]] = {}
    for r in rows:
        by_habit.setdefault(r.habit, set()).add(r.date)
    streaks = {h: compute_streak(days, date.today()) for h, days in by_habit.items()}
    habits_today = sorted(h for h, days in by_habit.items() if date.today() in days)

    week = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        week.append(sum(1 for days in by_habit.values() if d in days))

    total_checkins = (await db.execute(
        select(func.count()).where(HabitLog.user_id == user.id))).scalar() or 0
    friends_count = (await db.execute(
        select(func.count()).where(Friendship.user_id == user.id,
                                   Friendship.status == "accepted"))).scalar() or 0

    max_days = max((g.days_clean for g in goals_out), default=0)
    earned = achievements_for(max_days, streaks, len(habits_today), friends_count)
    existing = {a.achievement_id for a in (await db.execute(
        select(UserAchievement).where(UserAchievement.user_id == user.id))).scalars()}
    new_ids = [a for a in earned if a not in existing]
    for aid in new_ids:
        db.add(UserAchievement(user_id=user.id, achievement_id=aid))
    if new_ids:
        await db.commit()

    stats = StatsOut(total_days=sum(g.days_clean for g in goals_out),
                     total_checkins=int(total_checkins),
                     best_streak=max(streaks.values(), default=0),
                     friends_count=int(friends_count),
                     started=min((g.start_date for g in goals), default=None))
    return MeOut(name=user.first_name, goals=goals_out, streaks=streaks,
                 habits_today=habits_today, achievements=sorted(earned),
                 stats=stats, week=week)

@router.get("/invite")
async def invite(user: User = Depends(get_current_user)):
    return {"link": f"https://t.me/{settings.bot_username}?start=ref_{user.tg_id}"}

@router.post("/goal", response_model=GoalOut, status_code=201)
async def add_goal(body: GoalIn, user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)):
    dup = (await db.execute(
        select(Goal).where(Goal.user_id == user.id, Goal.active.is_(True),
                           Goal.addiction_type == body.addiction_type))).scalars().first()
    if dup:
        raise HTTPException(409, "goal already active")
    sd = body.start_date or date.today()
    goal = Goal(user_id=user.id, addiction_type=body.addiction_type,
                custom_label=body.custom_label, start_date=sd,
                started_at=_started_at(sd, body.start_time))
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return _goal_out(goal)

@router.post("/goal/{goal_id}/restart", response_model=GoalOut)
async def restart_goal(goal_id: int, body: RestartIn | None = None,
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    goal = (await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))).scalar_one_or_none()
    if not goal:
        raise HTTPException(404, "goal not found")
    goal.active = False
    st = body.start_time if body else None
    new_goal = Goal(user_id=user.id, addiction_type=goal.addiction_type,
                    custom_label=goal.custom_label, start_date=date.today(),
                    started_at=_started_at(date.today(), st))
    db.add(new_goal)
    await db.commit()
    await db.refresh(new_goal)
    return _goal_out(new_goal)

@router.delete("/goal/{goal_id}", status_code=204)
async def drop_goal(goal_id: int, user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_db)):
    goal = (await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))).scalar_one_or_none()
    if not goal:
        raise HTTPException(404, "goal not found")
    goal.active = False
    await db.commit()
    return None

@router.patch("/name")
async def set_name(body: NameIn, user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)):
    user.first_name = body.name.strip()
    await db.commit()
    return {"ok": True}
