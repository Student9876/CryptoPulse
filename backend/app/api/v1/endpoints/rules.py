"""Alert rules management REST endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert_rule import AlertRule
from app.models.user import User
from app.rules.cached_rule import CachedRule
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleRead

router = APIRouter(prefix="/rules", tags=["Alert Rules"])


@router.get("/", response_model=List[AlertRuleRead])
async def list_user_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AlertRuleRead]:
    """Returns all active alert rules configured by the authenticated user."""
    stmt = (
        select(AlertRule)
        .where(AlertRule.user_id == current_user.id, AlertRule.is_active.is_(True))
        .order_by(AlertRule.id.desc())
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()
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

    # Immediately register in in-memory RuleEngine cache
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


@router.delete("/{rule_id}")
async def delete_user_rule(
    rule_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deletes an alert rule owned by the authenticated user."""
    stmt = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == current_user.id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule #{rule_id} not found or does not belong to you",
        )

    await db.delete(rule)
    await db.commit()

    # Unregister from in-memory cache
    rule_engine = getattr(request.app.state, "rule_engine", None)
    if rule_engine:
        rule_engine.unregister_rule(rule_id)

    return {"status": "deleted", "rule_id": rule_id}
