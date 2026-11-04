"""Market status Telegram command handler (/status)."""

from typing import Optional
from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command

from app.stream.window_manager import WindowManager

router = Router(name="status_command")


@router.message(Command("status"))
async def cmd_status(message: types.Message, window_engine: Optional[WindowManager] = None) -> None:
    if not window_engine:
        await message.answer("⚠️ Market data engine is still warming up. Try again in a moment.")
        return

    all_metrics = window_engine.get_all_metrics()
    if not all_metrics:
        await message.answer("⏳ Ingesting initial market trades. Please check back in a few seconds.")
        return

    lines = ["📊 <b>CryptoPulse Live Market Intelligence:</b>\n────────────────────────"]
    for sym, m in all_metrics.items():
        sign = "+" if m.price_change_5m_pct >= 0 else ""
        lines.append(
            f"<b>{sym}:</b> ${m.current_price:,.2f}\n"
            f"• 5m Move: {sign}{m.price_change_5m_pct:.2f}%\n"
            f"• 5m VWAP: ${m.vwap_5m:,.2f}\n"
            f"• Vol Spike: {m.volume_spike_ratio:.1f}x baseline\n"
            f"• Taker Flow: {m.taker_buy_ratio_pct:.1f}% Buys\n"
        )
    lines.append("────────────────────────\n<i>Type /alert to set custom notifications.</i>")

    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)

