"""drop legacy job_postings table

Revision ID: 9b2d4f1c6e77
Revises: 3e1c2f9d8a11
Create Date: 2026-04-03 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b2d4f1c6e77'
down_revision: Union[str, None] = '3e1c2f9d8a11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_job_postings_title'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_id'), table_name='job_postings')
    op.drop_table('job_postings')


def downgrade() -> None:
    op.create_table(
        'job_postings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('company', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('salary', sa.String(), nullable=True),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('ai_extracted_skills', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url'),
    )
    op.create_index(op.f('ix_job_postings_id'), 'job_postings', ['id'], unique=False)
    op.create_index(op.f('ix_job_postings_title'), 'job_postings', ['title'], unique=False)