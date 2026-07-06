"""source balance

Revision ID: a1b2c3d4e5f6
Revises: 30c333a57401
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '30c333a57401'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('balance', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('sources', sa.Column('balance_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('sources', sa.Column('low_balance_threshold', sa.Numeric(precision=12, scale=2),
                                       nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('sources', 'low_balance_threshold')
    op.drop_column('sources', 'balance_date')
    op.drop_column('sources', 'balance')
