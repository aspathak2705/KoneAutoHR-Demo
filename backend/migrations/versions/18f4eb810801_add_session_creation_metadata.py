"""add_session_creation_metadata

Revision ID: 18f4eb810801
Revises: 2230bc64e7ef
Create Date: 2026-08-04 16:13:28.956552

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18f4eb810801'
down_revision: Union[str, None] = '2230bc64e7ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('creation_mode', sa.String(), nullable=False, server_default='AI'))
    op.add_column('sessions', sa.Column('package_version', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column('package_path', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'package_path')
    op.drop_column('sessions', 'package_version')
    op.drop_column('sessions', 'creation_mode')
