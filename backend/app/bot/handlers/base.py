"""Base Telegram command handlers (/start and /help)."""

from typing import Optional
from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.user import User

router = Router(name="base_commands")


async def get_or_create_user(telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> User:
    """Retrieves an existing user by telegram_id or creates a new record."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            user = User(telegram_id=telegram_id, username=username, first_name=first_name, is_active=True)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif user.username != username or user.first_name != first_name:
            user.username = username
            user.first_name = first_name
            await session.commit()

        return user


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    welcome_text = (
        f"👋 Welcome to <b>CryptoPulse</b>, {user.first_name or 'Trader'}!\n\n"
        "I am your real-time cryptocurrency intelligence and alerting engine.\n\n"
        "⚡ <b>What I Can Do:</b>\n"
        "• Monitor live Binance trades in sub-millisecond windows\n"
        "• Calculate VWAP, 5m Momentum, and Volume Spikes\n"
        "• Alert you immediately when market conditions trigger\n\n"
        "📋 <b>Available Commands:</b>\n"
        "• /status — View live prices and 5m market metrics\n"
        "• /alert — Create a custom threshold alert\n"
        "• /alerts — View your active alert rules\n"
        "• /delete &lt;id&gt; — Remove an alert rule\n"
        "• /help — Full command syntax guide\n"
    )

    reply_markup = None
    if settings.MINI_APP_URL:
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🚀 Open CryptoPulse Dashboard", web_app=WebAppInfo(url=settings.MINI_APP_URL))]]
        )

    await message.answer(welcome_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    help_text = (
        "📖 <b>CryptoPulse Alert Syntax Guide:</b>\n\n"
        "<b>1. Target Price Alerts:</b>\n"
        "<code>/alert BTC &gt; 85000</code>\n\n"
        "<b>2. Percentage Momentum (% Change):</b>\n"
        "<code>/alert BTC chg &gt; 2.0 5m</code>\n"
        "<code>/alert SOL chg &lt; -3.0 15m</code>\n\n"
        "<b>3. Volume Spikes:</b>\n"
        "<code>/alert ETH vol &gt; 3.0</code> (3x normal volume)\n\n"
        "<b>4. Order Flow:</b>\n"
        "<code>/alert BTC flow &gt; 80</code> (80% taker buyers)\n\n"
        "<b>Manage Rules:</b>\n"
        "• <code>/alerts</code> — List your active rules\n"
        "• <code>/delete 12</code> — Delete rule #12\n"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

