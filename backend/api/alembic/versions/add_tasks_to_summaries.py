"""add tasks (JSONB) to Summaries for CRM action items

Revision ID: add_tasks_to_summaries
Revises: add_processing_metrics
Create Date: 2026-06-21 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'add_tasks_to_summaries'
down_revision: Union[str, None] = 'add_processing_metrics'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tasks JSONB column to Summaries table."""
    op.add_column(
        'Summaries',
        sa.Column('tasks', JSONB, nullable=True, default=list,
                  comment='Задачи / action items (description, assignee, deadline) для CRM')
    )


def downgrade() -> None:
    """Drop tasks column from Summaries table."""
    op.drop_column('Summaries', 'tasks')
