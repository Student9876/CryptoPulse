"""Unit tests for Telegram Mini App HMAC-SHA256 authentication and dependency."""

import hashlib
import hmac
import json
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, validate_telegram_init_data


def generate_valid_init_data(user_id: int = 12345678, username: str = "alice", bot_token: str = "test_bot_token") -> str:
    """Helper to synthesize validly signed Telegram Mini App initData string."""
    user_json = json.dumps({"id": user_id, "first_name": "Alice", "username": username}, separators=(',', ':'))
    raw_params = {
        "auth_date": "1730000000",
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": user_json,
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(raw_params.items()))
    secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
    sig_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    raw_params["hash"] = sig_hash
    return "&".join(f"{k}={v}" for k, v in raw_params.items())


def test_validate_telegram_init_data_success():
    token = "my_secret_token_123"
    init_data = generate_valid_init_data(user_id=777, username="bob", bot_token=token)
    user_data = validate_telegram_init_data(init_data, token)

    assert user_data is not None
    assert user_data["id"] == 777
    assert user_data["username"] == "bob"


def test_validate_telegram_init_data_tampered():
    token = "my_secret_token_123"
    init_data = generate_valid_init_data(user_id=777, username="bob", bot_token=token)

    # Tamper with the user ID in the query string
    tampered = init_data.replace("777", "999")
    assert validate_telegram_init_data(tampered, token) is None

    # Completely invalid format
    assert validate_telegram_init_data("not_an_init_data", token) is None


@pytest.mark.asyncio
async def test_get_current_user_dev_mode(db_session: AsyncSession):
    """Verifies that development mode bypass works when X-Dev-Telegram-Id is provided."""
    user = await get_current_user(x_dev_telegram_id=987654, db=db_session)
    assert user is not None
    assert user.telegram_id == 987654


@pytest.mark.asyncio
async def test_get_current_user_missing_header(db_session: AsyncSession):
    """Verifies that requests with no auth headers are rejected with 401 Unauthorized."""
    with pytest.raises(HTTPException) as exc:
        await get_current_user(db=db_session)
    assert exc.value.status_code == 401
