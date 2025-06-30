"""add_is_active_to_user_clean

Revision ID: 49de8302e446
Revises: cd2158d447e4
Create Date: 2025-06-30 02:29:12.246875

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49de8302e446'
down_revision: Union[str, Sequence[str], None] = 'cd2158d447e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the missing columns to the USER table
    with op.batch_alter_table('USER') as batch_op:
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('verification_code', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('code_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('USER') as batch_op:
        batch_op.drop_column('code_expires_at')
        batch_op.drop_column('verification_code')
        batch_op.drop_column('is_active')
