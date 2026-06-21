"""drop tasks JSONB column from Summaries (moved to MeetingTasks)

Revision ID: remove_tasks_from_summaries
Revises: create_meeting_tasks
Create Date: 2026-06-21 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'remove_tasks_from_summaries'
down_revision: Union[str, None] = 'create_meeting_tasks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop tasks column from Summaries table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("Summaries")]
    if "tasks" in columns:
        op.drop_column("Summaries", "tasks")


def downgrade() -> None:
    """Re-add tasks JSONB column to Summaries (for rollback only)."""
    op.add_column(
        "Summaries",
        sa.Column("tasks", sa.JSON, nullable=True, default=list),
    )
