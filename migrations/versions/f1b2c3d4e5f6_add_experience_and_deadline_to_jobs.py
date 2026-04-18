"""add experience and application_deadline to jobs

Revision ID: f1b2c3d4e5f6
Revises: e5a1c4d9b2f0
Create Date: 2026-04-17 20:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1b2c3d4e5f6"
down_revision: Union[str, None] = "e5a1c4d9b2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("experience", sa.String(length=50), nullable=True))
    op.add_column("jobs", sa.Column("application_deadline", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "application_deadline")
    op.drop_column("jobs", "experience")
