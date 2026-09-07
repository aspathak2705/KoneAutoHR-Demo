"""add_encryption_metadata_columns

Revision ID: e8f901a23b45
Revises: c7a912e94f10
Create Date: 2026-09-07 13:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e8f901a23b45'
down_revision: Union[str, None] = 'c7a912e94f10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('presentations', sa.Column('encryption_version', sa.Integer(), server_default='0', nullable=False))
    op.add_column('presentations', sa.Column('encryption_algorithm', sa.String(), nullable=True))
    op.add_column('presentations', sa.Column('key_id', sa.String(), nullable=True))
    op.add_column('presentations', sa.Column('wrapped_dek', sa.String(), nullable=True))
    op.add_column('presentations', sa.Column('nonce', sa.String(), nullable=True))

    op.add_column('employee_lists', sa.Column('encryption_version', sa.Integer(), server_default='0', nullable=False))
    op.add_column('employee_lists', sa.Column('encryption_algorithm', sa.String(), nullable=True))
    op.add_column('employee_lists', sa.Column('key_id', sa.String(), nullable=True))
    op.add_column('employee_lists', sa.Column('wrapped_dek', sa.String(), nullable=True))
    op.add_column('employee_lists', sa.Column('nonce', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('employee_lists', 'nonce')
    op.drop_column('employee_lists', 'wrapped_dek')
    op.drop_column('employee_lists', 'key_id')
    op.drop_column('employee_lists', 'encryption_algorithm')
    op.drop_column('employee_lists', 'encryption_version')

    op.drop_column('presentations', 'nonce')
    op.drop_column('presentations', 'wrapped_dek')
    op.drop_column('presentations', 'key_id')
    op.drop_column('presentations', 'encryption_algorithm')
    op.drop_column('presentations', 'encryption_version')
