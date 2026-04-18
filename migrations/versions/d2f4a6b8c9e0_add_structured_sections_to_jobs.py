"""add structured job sections to jobs

Revision ID: d2f4a6b8c9e0
Revises: c7d9e2a4f1b3
Create Date: 2026-04-17 18:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2f4a6b8c9e0"
down_revision: Union[str, None] = "c7d9e2a4f1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("role_responsibilities", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("skills_qualifications", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("benefits", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "benefits")
    op.drop_column("jobs", "skills_qualifications")
    op.drop_column("jobs", "role_responsibilities")
