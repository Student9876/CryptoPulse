"""Alert history REST endpoints for audit trail retrieval and management."""

import math
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert_history import AlertHistory
from app.models.user import User
from app.schemas.alert_rule import AlertHistoryRead, PaginatedHistoryResponse

router = APIRouter(prefix="/history", tags=["Alert History"])


@router.get("/", response_model=Union[PaginatedHistoryResponse, List[AlertHistoryRead]])
async def list_alert_history(
    response: Response,
    page: Optional[int] = Query(None, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    symbol: Optional[str] = Query(None, description="Optional symbol filter, e.g. BTCUSDT"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Union[PaginatedHistoryResponse, List[AlertHistoryRead]]:
    """Returns chronologically ordered audit logs of triggered alerts with optional pagination."""
    base_stmt = select(AlertHistory).where(AlertHistory.user_id == current_user.id)
    if symbol:
        base_stmt = base_stmt.where(AlertHistory.symbol == symbol.upper())

    count_stmt = select(func.count(AlertHistory.id)).where(AlertHistory.user_id == current_user.id)
    if symbol:
        count_stmt = count_stmt.where(AlertHistory.symbol == symbol.upper())
    total = (await db.execute(count_stmt)).scalar() or 0

    response.headers["X-Total-Count"] = str(total)

    if page is not None:
        offset = (page - 1) * limit
        stmt = base_stmt.order_by(AlertHistory.triggered_at.desc(), AlertHistory.id.desc()).offset(offset).limit(limit)
        items = (await db.execute(stmt)).scalars().all()
        pages = math.ceil(total / limit) if total > 0 else 1
        return PaginatedHistoryResponse(
            items=[AlertHistoryRead.model_validate(r) for r in items],
            total=total,
            page=page,
            pages=pages,
            limit=limit,
        )

    stmt = base_stmt.order_by(AlertHistory.triggered_at.desc(), AlertHistory.id.desc()).limit(limit)
    records = (await db.execute(stmt)).scalars().all()
    return [AlertHistoryRead.model_validate(r) for r in records]


@router.delete("/", status_code=status.HTTP_200_OK)
async def clear_alert_history(
    symbol: Optional[str] = Query(None, description="Optional symbol filter to clear, e.g. BTCUSDT"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clears all or symbol-specific audit alert history for the authenticated user."""
    stmt = delete(AlertHistory).where(AlertHistory.user_id == current_user.id)
    if symbol:
        stmt = stmt.where(AlertHistory.symbol == symbol.upper())

    result = await db.execute(stmt)
    await db.commit()
    return {"status": "cleared", "deleted_count": result.rowcount}
