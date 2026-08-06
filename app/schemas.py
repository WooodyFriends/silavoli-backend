from datetime import date, datetime
from pydantic import BaseModel, Field

HABIT_PATTERN = r"^(steps|sport|read|water|sleep|calm|nosugar|outdoor)$"
ADDICTION_PATTERN = r"^(smoke|alcohol|drugs|gamble|custom)$"
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"

class AuthIn(BaseModel):
    init_data: str = Field(min_length=10)

class AuthOut(BaseModel):
    token: str
    name: str
    user_id: int

class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)

class GoalIn(BaseModel):
    addiction_type: str = Field(pattern=ADDICTION_PATTERN)
    custom_label: str | None = Field(default=None, max_length=60)
    start_date: date | None = None
    start_time: str | None = Field(default=None, pattern=TIME_PATTERN)

class RestartIn(BaseModel):
    start_time: str | None = Field(default=None, pattern=TIME_PATTERN)

class GoalOut(BaseModel):
    id: int
    addiction_type: str
    custom_label: str | None
    start_date: date
    started_at: datetime | None
    days_clean: int

class StatsOut(BaseModel):
    total_days: int
    total_checkins: int
    best_streak: int
    friends_count: int
    started: date | None

class MeOut(BaseModel):
    name: str
    goals: list[GoalOut]
    streaks: dict[str, int]
    habits_today: list[str]
    achievements: list[str]
    stats: StatsOut
    week: list[int]

class CheckIn(BaseModel):
    habit: str = Field(pattern=HABIT_PATTERN)
    check_date: date | None = None

class CheckOut(BaseModel):
    ok: bool
    streak: int
