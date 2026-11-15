"""Background worker consuming AlertEvents and delivering push notifications."""

import asyncio
from typing import Optional
from aiogram import Bot
from aiogram.enums import ParseMode
from sqlalchemy import update

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule, MetricType
from app.rules.evaluator import RuleEngine
from app.schemas.events import AlertEvent

logger = get_logger("cryptopulse.dispatcher")


class AlertDispatcher:
    """Consumes the in-memory alert queue, calls Telegram Bot API, and saves to database."""

    def __init__(self, rule_engine: RuleEngine, bot: Optional[Bot] = None) -> None:
        self.rule_engine = rule_engine
        self.bot = bot
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

    async def _dispatch_loop(self) -> None:
        logger.info("Alert dispatcher worker started")
        while self._running:
            try:
                event: AlertEvent = await self.rule_engine.alert_queue.get()

                # 1. Telegram Push Notification
                if self.bot and event.telegram_id:
                    try:
                        await self.bot.send_message(chat_id=event.telegram_id, text=event.message, parse_mode=ParseMode.HTML)
                        logger.info("Delivered Telegram alert for rule #%d to chat #%d", event.rule_id, event.telegram_id)
                    except Exception as err:
                        logger.error("Failed to send Telegram message to #%d: %s", event.telegram_id, err)

                # 2. Database Audit Persistence & One-Shot Price Target Deactivation
                try:
                    async with AsyncSessionLocal() as session:
                        session.add(AlertHistory(
                            user_id=event.user_id,
                            rule_id=event.rule_id,
                            symbol=event.symbol,
                            metric_value=event.actual_value,
                            threshold_value=event.threshold_value,
                            message=event.message,
                            triggered_at=event.triggered_at,
                        ))

                        if event.metric_type == MetricType.PRICE_LEVEL.value:
                            await session.execute(
                                update(AlertRule)
                                .where(AlertRule.id == event.rule_id)
                                .values(is_active=False)
                            )
                            self.rule_engine.unregister_rule(event.rule_id)
                            logger.info("Price target achieved for rule #%d. Auto-deactivated.", event.rule_id)

                        await session.commit()
                except Exception as db_err:
                    logger.error("Failed to persist alert history: %s", db_err)

                self.rule_engine.alert_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in alert dispatch loop: %s", exc, exc_info=True)

    def start(self) -> asyncio.Task:
        self._running = True
        self._task = asyncio.create_task(self._dispatch_loop(), name="alert-dispatcher-worker")
        return self._task

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

