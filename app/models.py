from datetime import date, datetime
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(64), default="Боец")
    photo_url: Mapped[str | None]
    referred_by: Mapped[int | None] = mapped_column(BigInteger)
    tz_offset: Mapped[int | None] = mapped_column(Integer, default=3)
    notify_hour: Mapped[int | None] = mapped_column(Integer, default=20)
    notify_enabled: Mapped[bool | None] = mapped_column(Boolean, default=True)
    last_notify_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    addiction_type: Mapped[str] = mapped_column(String(16))
    custom_label: Mapped[str | None] = mapped_column(String(60))
    start_date: Mapped[date]
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at_ts: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class HabitLog(Base):
    __tablename__ = "habit_logs"
    __table_args__ = (UniqueConstraint("user_id", "habit", "date", name="uq_habit_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    habit: Mapped[str] = mapped_column(String(16))
    date: Mapped[date]

class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_ach"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    achievement_id: Mapped[str] = mapped_column(String(20))
    unlocked_at: Mapped[datetime] = mapped_column(server_default=func.now())

class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="uq_friendship"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    friend_id: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")

class RehabCenter(Base):
    __tablename__ = "rehab_centers"
    id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(String(16), default="free")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

class PendingRef(Base):
    __tablename__ = "pending_refs"
    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger)
