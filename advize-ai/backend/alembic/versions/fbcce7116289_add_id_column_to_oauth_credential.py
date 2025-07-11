"""Add id column to OAUTH_CREDENTIAL

Revision ID: fbcce7116289
Revises: 49de8302e446
Create Date: 2025-07-01 00:06:47.269475

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fbcce7116289'
down_revision: Union[str, Sequence[str], None] = '49de8302e446'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('OAUTH_CREDENTIAL', sa.Column('id', sa.Integer(), nullable=False))
    op.alter_column('OAUTH_CREDENTIAL', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('OAUTH_CREDENTIAL', 'access_token',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('OAUTH_CREDENTIAL', 'connected_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False)
    op.alter_column('OAUTH_CREDENTIAL', 'is_verified',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.create_index(op.f('ix_OAUTH_CREDENTIAL_id'), 'OAUTH_CREDENTIAL', ['id'], unique=False)
    op.create_unique_constraint(None, 'OAUTH_CREDENTIAL', ['user_id'])
    op.drop_constraint(op.f('OAUTH_CREDENTIAL_user_id_fkey'), 'OAUTH_CREDENTIAL', type_='foreignkey')
    op.create_foreign_key(None, 'OAUTH_CREDENTIAL', 'USER', ['user_id'], ['id'], ondelete='CASCADE')
    op.alter_column('USER', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False)
    op.alter_column('USER', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('USER', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('USER', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
    op.drop_constraint(None, 'OAUTH_CREDENTIAL', type_='foreignkey')
    op.create_foreign_key(op.f('OAUTH_CREDENTIAL_user_id_fkey'), 'OAUTH_CREDENTIAL', 'USER', ['user_id'], ['id'])
    op.drop_constraint(None, 'OAUTH_CREDENTIAL', type_='unique')
    op.drop_index(op.f('ix_OAUTH_CREDENTIAL_id'), table_name='OAUTH_CREDENTIAL')
    op.alter_column('OAUTH_CREDENTIAL', 'is_verified',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('OAUTH_CREDENTIAL', 'connected_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
    op.alter_column('OAUTH_CREDENTIAL', 'access_token',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('OAUTH_CREDENTIAL', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_column('OAUTH_CREDENTIAL', 'id')
    # ### end Alembic commands ###
