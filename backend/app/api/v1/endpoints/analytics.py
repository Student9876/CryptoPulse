"""Market intelligence and rolling analytics REST endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.analytics import MarketOverview, SymbolAnalytics
from app.stream.window_manager import WindowManager

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_window_manager(request: Request) -> WindowManager:
    """Helper retrieving the WindowManager singleton from application state."""
    manager = getattr(request.app.state, "window_engine", None)
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics streaming engine is not initialized",
        )
    return manager


@router.get("/overview", response_model=MarketOverview)
async def get_market_overview(request: Request) -> MarketOverview:
    """Returns top movers, volume surges, and live metrics for all tracked pairs."""
    manager = get_window_manager(request)
    feed_status = "connected"

    ws_client = getattr(request.app.state, "ws_client", None)
    if ws_client and not ws_client.is_connected:
        feed_status = "reconnecting"

    rule_engine = getattr(request.app.state, "rule_engine", None)
    active_count = len(rule_engine.rules) if rule_engine else 0

    return manager.get_market_overview(
        feed_status=feed_status,
        active_alerts_count=active_count,
    )


@router.get("/{symbol}", response_model=SymbolAnalytics)
async def get_symbol_analytics(symbol: str, request: Request) -> SymbolAnalytics:
    """Returns rolling metrics and 30-minute sparkline chart points for an asset."""
    manager = get_window_manager(request)
    analytics = manager.get_analytics(symbol)

    if not analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{symbol.upper()}' not found or no market data available",
        )
    return analytics
