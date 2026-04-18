"""add employment_type to jobs

Revision ID: e5a1c4d9b2f0
Revises: d2f4a6b8c9e0
Create Date: 2026-04-17 20:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5a1c4d9b2f0"
down_revision: Union[str, None] = "d2f4a6b8c9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("employment_type", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "employment_type")
