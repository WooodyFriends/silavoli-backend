from datetime import datetime
from aiogram.types import LabeledPrice
from fastapi import APIRouter, Depends
from ..bot import bot
from ..config import settings
from ..deps import get_current_user
from ..models import User

router = APIRouter(prefix="/api/premium", tags=["premium"])

@router.get("/info")
async def info(user: User = Depends(get_current_user)):
    now = datetime.now()
    return {
        "price": settings.premium_price_stars,
        "is_premium": bool(user.premium_until and user.premium_until > now),
        "premium_until": user.premium_until.isoformat() if user.premium_until else None,
    }

@router.post("/invoice")
async def create_invoice(user: User = Depends(get_current_user)):
    link = await bot.create_invoice_link(
        title="«Сила воли» — подписка на 30 дней",
                description="Сообщество поддержки: собрания и группы, встречи с психологом, 12 шагов "
,
        payload=f"premium_{user.tg_id}",
        currency="XTR",
        prices=[LabeledPrice(label="30 дней", amount=settings.premium_price_stars)],
        subscription_period=30 * 24 * 3600,  # автопродление раз в месяц
    )
    return {"link": link}
