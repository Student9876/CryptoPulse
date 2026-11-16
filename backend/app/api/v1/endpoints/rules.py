"""Alert rules management REST endpoints."""

import math
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert_rule import AlertRule
from app.models.user import User
from app.rules.cached_rule import CachedRule
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleRead, AlertRuleUpdate, PaginatedRulesResponse

router = APIRouter(prefix="/rules", tags=["Alert Rules"])


@router.get("/", response_model=Union[PaginatedRulesResponse, List[AlertRuleRead]])
async def list_user_rules(
    response: Response,
    page: Optional[int] = Query(None, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(True, description="Filter by active status. Default True hides triggered one-time rules."),
    symbol: Optional[str] = Query(None, description="Optional symbol filter, e.g. BTCUSDT"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Union[PaginatedRulesResponse, List[AlertRuleRead]]:
    """Returns alert rules configured by the authenticated user with optional pagination."""
    base_stmt = select(AlertRule).where(AlertRule.user_id == current_user.id)
    if is_active is not None:
        base_stmt = base_stmt.where(AlertRule.is_active.is_(is_active))
    if symbol:
        base_stmt = base_stmt.where(AlertRule.symbol == symbol.upper())

    count_stmt = select(func.count(AlertRule.id)).where(AlertRule.user_id == current_user.id)
    if is_active is not None:
        count_stmt = count_stmt.where(AlertRule.is_active.is_(is_active))
    if symbol:
        count_stmt = count_stmt.where(AlertRule.symbol == symbol.upper())
    total = (await db.execute(count_stmt)).scalar() or 0

    response.headers["X-Total-Count"] = str(total)

    if page is not None:
        offset = (page - 1) * limit
        stmt = base_stmt.order_by(AlertRule.id.desc()).offset(offset).limit(limit)
        items = (await db.execute(stmt)).scalars().all()
        pages = math.ceil(total / limit) if total > 0 else 1
        return PaginatedRulesResponse(
            items=[AlertRuleRead.model_validate(r) for r in items],
            total=total,
            page=page,
            pages=pages,
            limit=limit,
        )

    stmt = base_stmt.order_by(AlertRule.id.desc()).limit(limit)
    rules = (await db.execute(stmt)).scalars().all()
    return [AlertRuleRead.model_validate(r) for r in rules]


@router.post("/", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
async def create_user_rule(
    rule_in: AlertRuleCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlertRuleRead:
    """Creates a new alert rule in database and immediately registers it into RAM engine."""
    symbol = rule_in.symbol.upper()
    db_rule = AlertRule(
        user_id=current_user.id,
        symbol=symbol,
        metric_type=rule_in.metric_type.value,
        condition=rule_in.condition.value,
        threshold_value=rule_in.threshold_value,
        window_seconds=rule_in.window_seconds,
        cooldown_seconds=rule_in.cooldown_seconds,
        is_recurring=rule_in.is_recurring,
        is_active=True,
    )
    db.add(db_rule)
    await db.commit()
    await db.refresh(db_rule)

    rule_engine = getattr(request.app.state, "rule_engine", None)
    if rule_engine:
        rule_engine.register_rule(CachedRule(
            id=db_rule.id,
            user_id=current_user.id,
            telegram_id=current_user.telegram_id,
            symbol=symbol,
            metric_type=db_rule.metric_type,
            condition=db_rule.condition,
            threshold_value=db_rule.threshold_value,
            window_seconds=db_rule.window_seconds,
            cooldown_seconds=db_rule.cooldown_seconds,
            is_recurring=db_rule.is_recurring,
            is_active=True,
        ))

    return AlertRuleRead.model_validate(db_rule)


@router.patch("/{rule_id}", response_model=AlertRuleRead)
async def update_user_rule(
    rule_id: int,
    rule_update: AlertRuleUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlertRuleRead:
    """Updates an alert rule (toggle active/pause, threshold, cooldown, or recurring)."""
    stmt = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == current_user.id)
    rule = (await db.execute(stmt)).scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule #{rule_id} not found or does not belong to you",
        )

    if rule_update.is_active is not None:
        rule.is_active = rule_update.is_active
    if rule_update.threshold_value is not None:
        rule.threshold_value = rule_update.threshold_value
    if rule_update.cooldown_seconds is not None:
        rule.cooldown_seconds = rule_update.cooldown_seconds
    if rule_update.is_recurring is not None:
        rule.is_recurring = rule_update.is_recurring

    await db.commit()
    await db.refresh(rule)

    rule_engine = getattr(request.app.state, "rule_engine", None)
    if rule_engine:
        if rule.is_active:
            rule_engine.register_rule(CachedRule(
                id=rule.id,
                user_id=current_user.id,
                telegram_id=current_user.telegram_id,
                symbol=rule.symbol,
                metric_type=rule.metric_type,
                condition=rule.condition,
                threshold_value=rule.threshold_value,
                window_seconds=rule.window_seconds,
                cooldown_seconds=rule.cooldown_seconds,
                is_recurring=rule.is_recurring,
                is_active=True,
            ))
        else:
            rule_engine.unregister_rule(rule.id)

    return AlertRuleRead.model_validate(rule)


@router.delete("/{rule_id}")
async def delete_user_rule(
    rule_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deletes an alert rule owned by the authenticated user."""
    stmt = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == current_user.id)
    rule = (await db.execute(stmt)).scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule #{rule_id} not found or does not belong to you",
        )

    await db.delete(rule)
    await db.commit()

    rule_engine = getattr(request.app.state, "rule_engine", None)
    if rule_engine:
        rule_engine.unregister_rule(rule_id)

    return {"status": "deleted", "rule_id": rule_id}
