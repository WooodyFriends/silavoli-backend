from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_db
from .models import User
from .security import AuthError, decode_jwt

bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(401, "unauthorized")
    try:
        tg_id = decode_jwt(creds.credentials)
    except AuthError:
        raise HTTPException(401, "unauthorized")
    user = (await db.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "unknown user")
    return user
