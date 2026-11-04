"""Combines sub-command routers into the primary bot router."""

from aiogram import Router

from app.bot.handlers.alerts import router as alerts_router
from app.bot.handlers.base import router as base_router
from app.bot.handlers.status import router as status_router

main_bot_router = Router(name="main_bot_router")
main_bot_router.include_router(base_router)
main_bot_router.include_router(status_router)
main_bot_router.include_router(alerts_router)

