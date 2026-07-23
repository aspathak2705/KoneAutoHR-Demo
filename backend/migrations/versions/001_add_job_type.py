"""add_job_type_to_presentation_jobs

Revision ID: 001_add_job_type
Revises: None
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_add_job_type'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('presentation_jobs', sa.Column('job_type', sa.String(), nullable=False, server_default='SCRIPT'))

def downgrade() -> None:
    op.drop_column('presentation_jobs', 'job_type')
