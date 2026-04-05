"""enforce job skill importance tiers

Revision ID: b4f8d2a1c3e9
Revises: 9b2d4f1c6e77
Create Date: 2026-04-03 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f8d2a1c3e9'
down_revision: Union[str, None] = '9b2d4f1c6e77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE job_skills
            SET importance = CASE
                WHEN importance IS NULL THEN 2.0
                WHEN importance >= 2.5 THEN 3.0
                WHEN importance >= 1.5 THEN 2.0
                WHEN importance > 1.0 THEN 1.0
                WHEN importance >= 0.8 THEN 3.0
                WHEN importance >= 0.55 THEN 2.0
                ELSE 1.0
            END
            """
        )
    )
    op.alter_column('job_skills', 'importance', existing_type=sa.Float(), nullable=False)
    op.create_check_constraint(
        'ck_job_skills_importance_tier',
        'job_skills',
        'importance IN (1.0, 2.0, 3.0)',
    )


def downgrade() -> None:
    op.drop_constraint('ck_job_skills_importance_tier', 'job_skills', type_='check')
    op.alter_column('job_skills', 'importance', existing_type=sa.Float(), nullable=True)