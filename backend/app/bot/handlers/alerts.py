"""Alert rule management Telegram command handlers (/alert, /alerts, /delete)."""

from typing import Optional
from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from sqlalchemy import select

from app.bot.handlers.base import get_or_create_user
from app.bot.parser import parse_alert_command
from app.db.session import AsyncSessionLocal
from app.models.alert_rule import AlertRule, ConditionType
from app.rules.cached_rule import CachedRule
from app.rules.evaluator import RuleEngine

router = Router(name="alert_commands")


@router.message(Command("alert"))
async def cmd_create_alert(message: types.Message, rule_engine: Optional[RuleEngine] = None) -> None:
    parsed = parse_alert_command(message.text or "")
    if not parsed:
        await message.answer(
            "❌ Invalid format. Examples:\n"
            "• <code>/alert BTC &gt; 85000</code>\n"
            "• <code>/alert ETH chg &gt; 2.5 5m</code>\n"
            "• <code>/alert SOL vol &gt; 3.0</code>\n"
            "Type /help for full guide.",
            parse_mode=ParseMode.HTML,
        )
        return

    symbol, metric_type, condition, threshold, window_sec = parsed
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    async with AsyncSessionLocal() as session:
        db_rule = AlertRule(
            user_id=user.id,
            symbol=symbol,
            metric_type=metric_type,
            condition=condition,
            threshold_value=threshold,
            window_seconds=window_sec,
            cooldown_seconds=600,
            is_active=True,
        )
        session.add(db_rule)
        await session.commit()
        await session.refresh(db_rule)

        if rule_engine:
            rule_engine.register_rule(CachedRule(
                id=db_rule.id,
                user_id=user.id,
                telegram_id=user.telegram_id,
                symbol=symbol,
                metric_type=metric_type,
                condition=condition,
                threshold_value=threshold,
                window_seconds=window_sec,
                cooldown_seconds=600,
                is_active=True,
            ))

    op = ">=" if condition == ConditionType.GREATER_THAN.value else "<="
    await message.answer(
        f"✅ <b>Alert Rule #{db_rule.id} Created!</b>\n"
        f"• Asset: <b>{symbol}</b>\n"
        f"• Metric: {metric_type}\n"
        f"• Trigger: {op} {threshold}\n"
        f"• Cooldown: 10m\n\n"
        f"<i>I will notify you here when triggered.</i>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("alerts"))
async def cmd_list_alerts(message: types.Message) -> None:
    user = await get_or_create_user(telegram_id=message.from_user.id)
    async with AsyncSessionLocal() as session:
        stmt = select(AlertRule).where(AlertRule.user_id == user.id, AlertRule.is_active.is_(True)).order_by(AlertRule.id.desc())
        rules = (await session.execute(stmt)).scalars().all()

    if not rules:
        await message.answer("📭 You have no active alert rules.\nCreate one: <code>/alert BTC &gt; 85000</code>", parse_mode=ParseMode.HTML)
        return

    lines = ["📋 <b>Your Active Alert Rules:</b>\n────────────────────────"]
    for r in rules:
        op = ">=" if r.condition == ConditionType.GREATER_THAN.value else "<="
        lines.append(f"• <b>#{r.id}</b> | <b>{r.symbol}</b> {r.metric_type} {op} {r.threshold_value}")
    lines.append("────────────────────────\n<i>To delete a rule: /delete &lt;id&gt;</i>")
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


@router.message(Command("delete"))
async def cmd_delete_alert(message: types.Message, rule_engine: Optional[RuleEngine] = None) -> None:
    parts = (message.text or "").strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("❌ Usage: <code>/delete &lt;rule_id&gt;</code>\nExample: <code>/delete 5</code>", parse_mode=ParseMode.HTML)
        return

    rule_id = int(parts[1])
    user = await get_or_create_user(telegram_id=message.from_user.id)

    async with AsyncSessionLocal() as session:
        stmt = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user.id)
        rule = (await session.execute(stmt)).scalar_one_or_none()
        if not rule:
            await message.answer(f"⚠️ Rule #{rule_id} not found or does not belong to you.")
            return

        await session.delete(rule)
        await session.commit()
        if rule_engine:
            rule_engine.unregister_rule(rule_id)

    await message.answer(f"🗑️ Alert rule #{rule_id} deleted successfully.")

