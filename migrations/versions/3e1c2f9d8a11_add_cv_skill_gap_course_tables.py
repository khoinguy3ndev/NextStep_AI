"""add cv skill gap course tables

Revision ID: 3e1c2f9d8a11
Revises: 7bfb3f0a64bf
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e1c2f9d8a11'
down_revision: Union[str, None] = '7bfb3f0a64bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cv_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default=sa.text('0.5')),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='regex'),
        sa.ForeignKeyConstraint(['analysis_id'], ['cv_analysis_results.analysis_id']),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_cv_skills_id'), 'cv_skills', ['id'], unique=False)
    op.create_index(op.f('ix_cv_skills_analysis_id'), 'cv_skills', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_cv_skills_skill_id'), 'cv_skills', ['skill_id'], unique=False)

    op.create_table(
        'skill_gaps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('priority_score', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        sa.Column('gap_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['analysis_id'], ['cv_analysis_results.analysis_id']),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_skill_gaps_id'), 'skill_gaps', ['id'], unique=False)
    op.create_index(op.f('ix_skill_gaps_analysis_id'), 'skill_gaps', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_skill_gaps_skill_id'), 'skill_gaps', ['skill_id'], unique=False)

    op.create_table(
        'skill_courses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('duration', sa.String(length=50), nullable=True),
        sa.Column('level', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_skill_courses_id'), 'skill_courses', ['id'], unique=False)
    op.create_index(op.f('ix_skill_courses_skill_id'), 'skill_courses', ['skill_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_skill_courses_skill_id'), table_name='skill_courses')
    op.drop_index(op.f('ix_skill_courses_id'), table_name='skill_courses')
    op.drop_table('skill_courses')

    op.drop_index(op.f('ix_skill_gaps_skill_id'), table_name='skill_gaps')
    op.drop_index(op.f('ix_skill_gaps_analysis_id'), table_name='skill_gaps')
    op.drop_index(op.f('ix_skill_gaps_id'), table_name='skill_gaps')
    op.drop_table('skill_gaps')

    op.drop_index(op.f('ix_cv_skills_skill_id'), table_name='cv_skills')
    op.drop_index(op.f('ix_cv_skills_analysis_id'), table_name='cv_skills')
    op.drop_index(op.f('ix_cv_skills_id'), table_name='cv_skills')
    op.drop_table('cv_skills')