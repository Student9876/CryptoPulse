"""CryptoPulse FastAPI Application Entrypoint.

Initializes the FastAPI application, registers middleware (CORS),
manages startup/shutdown lifespans, and mounts core routing endpoints.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.bot import TelegramBotService
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.rules import RuleEngine
from app.schemas.events import TradeEvent
from app.stream import BinanceWebSocketClient, WindowManager

logger = get_logger("cryptopulse.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle: startup and shutdown events."""
    setup_logging()
    logger.info("Starting %s v%s...", settings.PROJECT_NAME, settings.VERSION)
    logger.info("Tracked symbols configured: %s", settings.TRACKED_SYMBOLS)

    # Initialize in-memory rolling window metrics engine and rule engine
    window_engine = WindowManager(symbols=settings.TRACKED_SYMBOLS)
    rule_engine = RuleEngine()
    app.state.window_engine = window_engine
    app.state.rule_engine = rule_engine

    # Initialize Telegram Bot service and background alert dispatcher
    bot_service = TelegramBotService(rule_engine=rule_engine, window_engine=window_engine)
    await bot_service.start()
    app.state.bot_service = bot_service

    ws_client: Optional[BinanceWebSocketClient] = None

    if settings.ENABLE_INGESTION:
        # Throttle periodic terminal metrics logging to once per 2 seconds per symbol
        last_logged_at: Dict[str, float] = {}

        async def on_trade_received(trade: TradeEvent) -> None:
            """Feeds incoming trade into sliding window and evaluates alert rules."""
            window_engine.process_trade(trade)

            metrics = window_engine.get_metrics(trade.symbol)
            if metrics:
                # 1. Evaluate active alert rules
                alerts = rule_engine.evaluate_metrics(metrics)
                for alert in alerts:
                    logger.warning(
                        "DISPATCH QUEUE: Alert generated for user %d (Rule #%d on %s)",
                        alert.user_id,
                        alert.rule_id,
                        alert.symbol,
                    )

                # 2. Check if 2 seconds have elapsed since last terminal summary for this symbol
                now_ts = datetime.now(timezone.utc).timestamp()
                last_ts = last_logged_at.get(trade.symbol, 0.0)

                if now_ts - last_ts >= 2.0:
                    last_logged_at[trade.symbol] = now_ts
                    sign = "+" if metrics.price_change_5m_pct >= 0 else ""
                    logger.info(
                        "METRICS | %-8s | $%10.2f | 5m: %s%5.2f%% | VWAP: $%10.2f | "
                        "VolSpike: %4.1fx | TakerBuy: %4.1f%% | TPS: %-4.1f",
                        metrics.symbol,
                        metrics.current_price,
                        sign,
                        metrics.price_change_5m_pct,
                        metrics.vwap_5m,
                        metrics.volume_spike_ratio,
                        metrics.taker_buy_ratio_pct,
                        metrics.trades_per_second,
                    )

        logger.info("Initializing Binance live market ingestion...")
        ws_client = BinanceWebSocketClient(on_trade=on_trade_received)
        ws_client.start()
        app.state.ws_client = ws_client

    yield

    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    if ws_client:
        await ws_client.stop()
    if bot_service:
        await bot_service.stop()


def create_application() -> FastAPI:
    """Factory function to build and configure the FastAPI app instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Real-Time Cryptocurrency Market Intelligence & Alerting Engine",
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing (CORS) setup for frontend and TMA
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API version 1 endpoints
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    @app.get("/healthz", tags=["Health"])
    async def health_check() -> dict:
        """Basic health check endpoint for monitoring and uptime verification."""
        feed_health = None
        if hasattr(app.state, "ws_client") and app.state.ws_client:
            feed_health = app.state.ws_client.get_health_status()

        return {
            "status": "ok",
            "app": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "feed": feed_health,
        }

    return app


# Application instance for ASGI servers (e.g. uvicorn app.main:app)
app = create_application()

