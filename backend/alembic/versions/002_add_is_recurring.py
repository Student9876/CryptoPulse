"""Add is_recurring column to alert_rules

Revision ID: 002_add_is_recurring
Revises: 001_initial_schema
Create Date: 2026-11-15 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_is_recurring'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'alert_rules',
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('alert_rules', 'is_recurring')
