"""Alert history REST endpoints for audit trail retrieval."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert_history import AlertHistory
from app.models.user import User
from app.schemas.alert_rule import AlertHistoryRead

router = APIRouter(prefix="/history", tags=["Alert History"])


@router.get("/", response_model=List[AlertHistoryRead])
async def list_alert_history(
    symbol: Optional[str] = Query(None, description="Optional symbol filter, e.g. BTCUSDT"),
    limit: int = Query(50, ge=1, le=200, description="Max audit entries to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AlertHistoryRead]:
    """Returns chronologically ordered audit logs of triggered alerts for the authenticated user."""
    stmt = select(AlertHistory).where(AlertHistory.user_id == current_user.id)
    if symbol:
        stmt = stmt.where(AlertHistory.symbol == symbol.upper())
    stmt = stmt.order_by(AlertHistory.triggered_at.desc(), AlertHistory.id.desc()).limit(limit)

    result = await db.execute(stmt)
    records = result.scalars().all()
    return [AlertHistoryRead.model_validate(r) for r in records]
