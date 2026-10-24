"""Alert history database model for triggered event audit trails."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.alert_rule import AlertRule


class AlertHistory(Base):
    """Immutable audit record created each time an alert rule condition is met."""

    __tablename__ = "alert_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # SET NULL preserves triggered history even if the parent rule is later deleted
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="alert_history")
    rule: Mapped[Optional["AlertRule"]] = relationship("AlertRule", back_populates="history")

    def __repr__(self) -> str:
        return (
            f"<AlertHistory id={self.id} symbol='{self.symbol}' "
            f"metric_value={self.metric_value} at={self.triggered_at}>"
        )

