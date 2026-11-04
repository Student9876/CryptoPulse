"""Application configuration settings managed via Pydantic.

Loads configuration from environment variables and an optional .env file.
Provides strongly typed access to critical system parameters.
"""

from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings fxxxor CryptoPulse."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Information
    PROJECT_NAME: str = Field(default="CryptoPulse", description="Project name")
    VERSION: str = Field(default="0.1.0", description="Version of the application")
    DEBUG: bool = Field(default=False, description="Enable debug mode and verbose log output")
    API_V1_STR: str = Field(default="/api/v1", description="Prefix for API version 1 routes")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: Union[bool, str]) -> bool:
        """Safely parses boolean debug flag even if environment has values like 'release' or 'dev'."""
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "dev", "development")
        return bool(value)

    # Allowed CORS Origins
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="Allowed cross-origin resource sharing origins for frontend clients",
    )

    # Database Configuration (PostgreSQL with asyncpg driver)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cryptopulse",
        description="Async PostgreSQL connection string",
    )

    # Binance WebSocket Market Ingestion
    # data-stream.binance.vision is Binance's official public market data gateway
    # (globally accessible without regional cloud/ISP IP blocks)
    BINANCE_WS_URL: str = Field(
        default="wss://data-stream.binance.vision/stream",
        description="Base WebSocket URL for Binance combined stream",
    )
    TRACKED_SYMBOLS: List[str] = Field(
        default=["btcusdt", "ethusdt", "solusdt"],
        description="List of trading pairs to ingest and compute metrics for",
    )
    ENABLE_INGESTION: bool = Field(
        default=True,
        description="Automatically start live market data ingestion on application startup",
    )

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",
        description="Bot authentication token provided by @BotFather",
    )
    TELEGRAM_WEBHOOK_URL: str = Field(
        default="",
        description="Public HTTPS endpoint where Telegram will deliver updates",
    )
    MINI_APP_URL: str = Field(
        default="",
        description="Public HTTPS URL where the Telegram Mini App frontend is hosted",
    )

    @field_validator("TRACKED_SYMBOLS", mode="before")
    @classmethod
    def normalize_symbols(cls, value: Union[str, List[str]]) -> List[str]:
        """Ensures all tracked symbols are lowercase strings without whitespaces."""
        if isinstance(value, str):
            # Split comma-separated string if provided via environment variable
            return [s.strip().lower() for s in value.split(",") if s.strip()]
        return [s.strip().lower() for s in value if isinstance(s, str)]


# Global settings singleton instance
settings = Settings()

