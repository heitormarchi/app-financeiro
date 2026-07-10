"""drop user_routines

Revision ID: c8e5a1f0b3d2
Revises: b7d3f091a2c4
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e5a1f0b3d2'
down_revision: Union[str, None] = 'b7d3f091a2c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'user_routines' in inspector.get_table_names():
        op.drop_table('user_routines')


def downgrade() -> None:
    op.create_table(
        'user_routines',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('work_start', sa.String(length=5), nullable=True),
        sa.Column('work_end', sa.String(length=5), nullable=True),
        sa.Column('work_days', sa.JSON(), nullable=True),
        sa.Column('patterns', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
