from datetime import date
from pydantic import BaseModel, ConfigDict, Field

class AuthIn(BaseModel):
    init_data: str = Field(min_length=10)

class AuthOut(BaseModel):
    token: str
    name: str

class GoalIn(BaseModel):
    addiction_type: str = Field(pattern=r"^(smoke|alcohol|drugs|gamble|custom)$")
    custom_label: str | None = Field(default=None, max_length=60)
    start_date: date

class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    addiction_type: str
    custom_label: str | None
    start_date: date

class MeOut(BaseModel):
    name: str
    days_clean: int
    goal: GoalOut | None
    streaks: dict[str, int]
    achievements: list[str]

class CheckIn(BaseModel):
    habit: str = Field(pattern=r"^(steps|sport|read)$")
    check_date: date | None = None

class CheckOut(BaseModel):
    ok: bool
    streak: int
