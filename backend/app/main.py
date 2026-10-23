"""CryptoPulse FastAPI Application Entrypoint.

Initializes the FastAPI application, registers middleware (CORS),
manages startup/shutdown lifespans, and mounts core routing endpoints.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger, setup_logging

logger = get_logger("cryptopulse.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle: startup and shutdown events."""
    setup_logging()
    logger.info("Starting %s v%s...", settings.PROJECT_NAME, settings.VERSION)
    logger.info("Tracked symbols configured: %s", settings.TRACKED_SYMBOLS)

    # In future milestones, background workers (Binance WS, Alert Dispatcher)
    # and database connections will initialize here.
    yield

    logger.info("Shutting down %s...", settings.PROJECT_NAME)


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
        return {
            "status": "ok",
            "app": settings.PROJECT_NAME,
            "version": settings.VERSION,
        }

    return app


# Application instance for ASGI servers (e.g. uvicorn app.main:app)
app = create_application()

