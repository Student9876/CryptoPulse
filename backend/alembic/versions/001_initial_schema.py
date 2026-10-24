"""Initial schema: users, alert_rules, alert_history

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-23 08:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create 'users' table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=True),
        sa.Column('first_name', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)

    # 2. Create 'alert_rules' table
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('metric_type', sa.String(length=32), nullable=False),
        sa.Column('condition', sa.String(length=16), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('window_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('cooldown_seconds', sa.Integer(), nullable=False, server_default='600'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_rules_user_id'), 'alert_rules', ['user_id'], unique=False)
    op.create_index(op.f('ix_alert_rules_symbol'), 'alert_rules', ['symbol'], unique=False)
    op.create_index(op.f('ix_alert_rules_metric_type'), 'alert_rules', ['metric_type'], unique=False)
    op.create_index(op.f('ix_alert_rules_is_active'), 'alert_rules', ['is_active'], unique=False)

    # 3. Create 'alert_history' table
    op.create_table(
        'alert_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=True),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_history_user_id'), 'alert_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_alert_history_rule_id'), 'alert_history', ['rule_id'], unique=False)
    op.create_index(op.f('ix_alert_history_symbol'), 'alert_history', ['symbol'], unique=False)
    op.create_index(op.f('ix_alert_history_triggered_at'), 'alert_history', ['triggered_at'], unique=False)


def downgrade() -> None:
    op.drop_table('alert_history')
    op.drop_table('alert_rules')
    op.drop_table('users')

