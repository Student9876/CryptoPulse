"""Centralized logging configuration for CryptoPulse.

Provides clean, structured, readable console logs for tracking:
- Ingestion events and connection states
- Metric computation intervals
- Alert trigger dispatches
- API request metrics and errors
"""

import logging
import sys
from app.core.config import settings


def setup_logging() -> None:
    """Configures root and application loggers with a standard formatter."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Custom clean log format
    log_format = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress overly noisy logs from third-party libraries unless in DEBUG mode
    if not settings.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("aiosqlite").setLevel(logging.WARNING)
        logging.getLogger("websockets").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Utility helper to get a named logger instance."""
    return logging.getLogger(name)

