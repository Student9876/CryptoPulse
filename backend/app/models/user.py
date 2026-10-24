"""User database model representing Telegram accounts."""

from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.alert_rule import AlertRule
    from app.models.alert_history import AlertHistory


class User(Base, TimestampMixin):
    """Stores Telegram user account metadata and preferences."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Telegram user IDs can exceed standard 32-bit integer limits (> 2 billion)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # One-to-many relationships
    alert_rules: Mapped[List["AlertRule"]] = relationship(
        "AlertRule",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    alert_history: Mapped[List["AlertHistory"]] = relationship(
        "AlertHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} username='{self.username}'>"

