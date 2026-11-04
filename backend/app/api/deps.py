"""FastAPI dependencies for Telegram Mini App authentication and session handling."""

import hashlib
import hmac
import json
import urllib.parse
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User


def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """Cryptographically verifies Telegram Mini App initData using HMAC-SHA256."""
    try:
        parsed_qsl = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        data_dict = dict(parsed_qsl)
        received_hash = data_dict.pop("hash", None)
        if not received_hash:
            return None

        # Sort remaining keys alphabetically and join with newlines
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))

        # Secret key = HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return None

        # Extract and parse user payload
        user_str = data_dict.get("user")
        return json.loads(user_str) if user_str else None
    except Exception:
        return None


async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: Optional[int] = Header(default=None, alias="X-Dev-Telegram-Id"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency validating Telegram identity and returning authenticated User model."""
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None

    # Safely extract raw values if called outside FastAPI dependency injection (e.g. unit tests)
    raw_dev_id = x_dev_telegram_id if isinstance(x_dev_telegram_id, int) else None
    raw_init_data = x_telegram_init_data if isinstance(x_telegram_init_data, str) and x_telegram_init_data else None

    # 1. Dev / Local Test Mode Bypass (allowed when token not set or in debug mode)
    if raw_dev_id and (settings.DEBUG or not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here"):
        telegram_id = raw_dev_id
        username = "dev_trader"
        first_name = "DevUser"

    # 2. Production Cryptographic Telegram initData Validation
    elif raw_init_data:
        token = settings.TELEGRAM_BOT_TOKEN.strip()
        user_data = validate_telegram_init_data(raw_init_data, token)
        if not user_data or "id" not in user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or forged Telegram authentication signature",
            )
        telegram_id = int(user_data["id"])
        username = user_data.get("username")
        first_name = user_data.get("first_name")

    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram authentication header (X-Telegram-Init-Data or X-Dev-Telegram-Id)",
        )

    # 3. Retrieve or auto-create User in PostgreSQL
    stmt = select(User).where(User.telegram_id == telegram_id)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name, is_active=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
