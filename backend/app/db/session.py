"""Asynchronous database connection engine and session factory."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

def get_async_engine_url(raw_url: str) -> str:
    """Defensively ensures asyncpg driver and valid SSL parameters are used."""
    url = str(raw_url)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "sslmode=" in url:
        url = url.replace("sslmode=", "ssl=")
    return url


# Initialize asynchronous engine with connection health checks
# pool_pre_ping=True tests connections prior to checkout to discard stale connections
engine: AsyncEngine = create_async_engine(
    get_async_engine_url(settings.DATABASE_URL),
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# Async session factory
# expire_on_commit=False prevents attributes from expiring after commit,
# which avoids unexpected lazy-loading errors in async code.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

