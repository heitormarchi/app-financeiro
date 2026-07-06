"""recurring rules

Revision ID: b7d3f091a2c4
Revises: a1b2c3d4e5f6
Create Date: 2026-07-06 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d3f091a2c4'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recurring_rules',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('entity', sa.String(length=10), nullable=False, server_default='pessoal'),
        sa.Column('source_id', sa.Uuid(), sa.ForeignKey('sources.id'), nullable=True),
        sa.Column('frequency', sa.String(length=10), nullable=False),
        sa.Column('day', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column('scheduled_transactions',
                   sa.Column('recurring_rule_id', sa.Uuid(), sa.ForeignKey('recurring_rules.id'), nullable=True))


def downgrade() -> None:
    op.drop_column('scheduled_transactions', 'recurring_rule_id')
    op.drop_table('recurring_rules')
