"""CryptoPulse FastAPI Application Entrypoint.

Initializes the FastAPI application, registers middleware (CORS),
manages startup/shutdown lifespans, and mounts core routing endpoints.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.schemas.events import TradeEvent
from app.services.binance_ws import BinanceWebSocketClient

logger = get_logger("cryptopulse.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle: startup and shutdown events."""
    setup_logging()
    logger.info("Starting %s v%s...", settings.PROJECT_NAME, settings.VERSION)
    logger.info("Tracked symbols configured: %s", settings.TRACKED_SYMBOLS)

    ws_client: Optional[BinanceWebSocketClient] = None

    if settings.ENABLE_INGESTION:
        async def on_trade_received(trade: TradeEvent) -> None:
            """Handler for real-time trade events."""
            aggressor = "BUY " if not trade.is_buyer_maker else "SELL"
            logger.info(
                "TRADE | %-8s | $%10.2f | Qty: %-8.4f | [%s]",
                trade.symbol,
                trade.price,
                trade.quantity,
                aggressor,
            )

        logger.info("Initializing Binance live market ingestion...")
        ws_client = BinanceWebSocketClient(on_trade=on_trade_received)
        ws_client.start()
        app.state.ws_client = ws_client

    yield

    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    if ws_client:
        await ws_client.stop()


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

