"""Pydantic schemas for AlertRule and AlertHistory entities."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.alert_rule import ConditionType, MetricType


class AlertRuleBase(BaseModel):
    symbol: str = Field(..., examples=["BTCUSDT"], description="Crypto asset symbol")
    metric_type: MetricType = Field(..., description="Target metric for condition evaluation")
    condition: ConditionType = Field(..., description="GREATER_THAN or LESS_THAN")
    threshold_value: float = Field(..., description="Numeric threshold to compare against")
    window_seconds: int = Field(default=300, ge=10, le=86400, description="Evaluation window duration in seconds")
    cooldown_seconds: int = Field(default=600, ge=0, le=86400, description="Cooldown suppression period in seconds")
    is_recurring: bool = Field(default=False, description="Whether alert repeats continuously after cooldown or deactivates upon first trigger")


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    is_active: Optional[bool] = None
    threshold_value: Optional[float] = None
    cooldown_seconds: Optional[int] = None
    is_recurring: Optional[bool] = None


class AlertRuleRead(AlertRuleBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertHistoryRead(BaseModel):
    id: int
    user_id: int
    rule_id: Optional[int]
    symbol: str
    metric_value: float
    threshold_value: float
    message: str
    triggered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedRulesResponse(BaseModel):
    items: List[AlertRuleRead]
    total: int
    page: int
    pages: int
    limit: int


class PaginatedHistoryResponse(BaseModel):
    items: List[AlertHistoryRead]
    total: int
    page: int
    pages: int
    limit: int

