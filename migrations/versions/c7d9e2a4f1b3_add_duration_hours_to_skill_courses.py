"""add duration_hours to skill_courses

Revision ID: c7d9e2a4f1b3
Revises: b4f8d2a1c3e9
Create Date: 2026-04-05 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7d9e2a4f1b3"
down_revision: Union[str, None] = "b4f8d2a1c3e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skill_courses", sa.Column("duration_hours", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("skill_courses", "duration_hours")
