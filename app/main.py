import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram.types import Update
from .config import settings
from .db import Base, engine
from .bot import bot, dp
from .routers import auth, friends, habits, me

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if settings.public_url:
        try:
            await bot.set_webhook(f"{settings.public_url}/bot/webhook")
            logging.info("webhook set")
        except Exception as e:
            logging.warning("webhook: %s", e)
    try:
        bot_me = await bot.get_me()
        if not settings.bot_username:
            settings.bot_username = bot_me.username
            logging.info("bot username: %s", bot_me.username)
    except Exception as e:
        logging.warning("get_me: %s", e)
    yield

app = FastAPI(title="Сила воли API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list,
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "sila-voli"}

@app.post("/bot/webhook")
async def tg_webhook(request: Request):
    await dp.feed_update(bot, Update.model_validate(await request.json()))
    return {"ok": True}

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(habits.router)
app.include_router(friends.router)
