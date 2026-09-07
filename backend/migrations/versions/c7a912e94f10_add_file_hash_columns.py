"""add_file_hash_columns

Revision ID: c7a912e94f10
Revises: 06ce74eada25
Create Date: 2026-09-07 10:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c7a912e94f10'
down_revision: Union[str, None] = '06ce74eada25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
 op.add_column('presentations', sa.Column('file_hash', sa.String(), nullable=True))
 op.create_index(op.f('ix_presentations_file_hash'), 'presentations', ['file_hash'], unique=False)
 op.add_column('employee_lists', sa.Column('file_hash', sa.String(), nullable=True))
 op.create_index(op.f('ix_employee_lists_file_hash'), 'employee_lists', ['file_hash'], unique=False)

def downgrade() -> None:
 op.drop_index(op.f('ix_employee_lists_file_hash'), table_name='employee_lists')
 op.drop_column('employee_lists', 'file_hash')
 op.drop_index(op.f('ix_presentations_file_hash'), table_name='presentations')
 op.drop_column('presentations', 'file_hash')
