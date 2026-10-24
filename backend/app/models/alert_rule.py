"""Alert rule database model for configurable user conditions."""

from enum import Enum
from typing import TYPE_CHECKING, List
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.alert_history import AlertHistory


class MetricType(str, Enum):
    """Supported market metrics for rule evaluation."""
    PRICE_CHANGE = "PRICE_CHANGE"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    VOLATILITY = "VOLATILITY"
    RANGE_BREAKOUT = "RANGE_BREAKOUT"
    TAKER_BUY_RATIO = "TAKER_BUY_RATIO"
    VWAP_CROSSOVER = "VWAP_CROSSOVER"


class ConditionType(str, Enum):
    """Comparison operator applied to the threshold."""
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"


class AlertRule(Base, TimestampMixin):
    """Stores user-defined threshold alert criteria for specific crypto assets."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    metric_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    condition: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Time window to evaluate (e.g. 300 seconds = 5 minutes)
    window_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    
    # Cooldown duration in seconds to silence duplicate alerts after triggering
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="alert_rules")
    history: Mapped[List["AlertHistory"]] = relationship("AlertHistory", back_populates="rule")

    def __repr__(self) -> str:
        return (
            f"<AlertRule id={self.id} user_id={self.user_id} symbol='{self.symbol}' "
            f"metric='{self.metric_type}' {self.condition} {self.threshold_value}>"
        )

