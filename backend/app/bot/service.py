"""Telegram bot lifecycle management and database preloading."""

import asyncio
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select

from app.bot.dispatcher import AlertDispatcher
from app.bot.handlers import main_bot_router
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.alert_rule import AlertRule
from app.models.user import User
from app.rules.cached_rule import CachedRule
from app.rules.evaluator import RuleEngine
from app.stream.window_manager import WindowManager

logger = get_logger("cryptopulse.telegram")


async def load_active_rules_into_engine(engine: RuleEngine) -> int:
    """Preloads active rules from PostgreSQL into the in-memory RuleEngine."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(AlertRule, User.telegram_id).join(User, AlertRule.user_id == User.id).where(AlertRule.is_active.is_(True))
            rows = (await session.execute(stmt)).all()

            for rule, telegram_id in rows:
                engine.register_rule(CachedRule(
                    id=rule.id,
                    user_id=rule.user_id,
                    telegram_id=telegram_id,
                    symbol=rule.symbol,
                    metric_type=rule.metric_type,
                    condition=rule.condition,
                    threshold_value=rule.threshold_value,
                    window_seconds=rule.window_seconds,
                    cooldown_seconds=rule.cooldown_seconds,
                    is_active=rule.is_active,
                ))
            logger.info("Loaded %d active alert rules from DB into memory", len(rows))
            return len(rows)
    except Exception as exc:
        logger.warning(
            "Could not preload alert rules from database: %s. Starting with empty in-memory rule cache.",
            exc,
        )
        return 0


class TelegramBotService:
    """Manages bot polling and the background alert dispatcher."""

    def __init__(self, rule_engine: RuleEngine, window_engine: WindowManager) -> None:
        self.rule_engine = rule_engine
        self.window_engine = window_engine
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.dispatcher_worker: Optional[AlertDispatcher] = None
        self._polling_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        await load_active_rules_into_engine(self.rule_engine)
        token = settings.TELEGRAM_BOT_TOKEN.strip()

        if not token or token == "your_telegram_bot_token_here":
            logger.warning("TELEGRAM_BOT_TOKEN not configured. Bot running in dormant mode.")
            self.dispatcher_worker = AlertDispatcher(self.rule_engine, bot=None)
            self.dispatcher_worker.start()
            return

        self.bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.dp = Dispatcher()
        self.dp.include_router(main_bot_router)
        self.dp["rule_engine"] = self.rule_engine
        self.dp["window_engine"] = self.window_engine

        self.dispatcher_worker = AlertDispatcher(self.rule_engine, bot=self.bot)
        self.dispatcher_worker.start()

        logger.info("Starting Telegram Bot polling...")
        self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot, handle_signals=False), name="tg-polling")

    async def stop(self) -> None:
        if self.dispatcher_worker:
            await self.dispatcher_worker.stop()
        if self.dp and self.bot:
            await self.dp.stop_polling()
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        if self.bot:
            await self.bot.session.close()
