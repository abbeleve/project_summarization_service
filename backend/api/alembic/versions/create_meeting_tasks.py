"""create MeetingTasks table for per-task CRM tracking

Revision ID: create_meeting_tasks
Revises: add_weeek_api_token_to_staff
Create Date: 2026-06-21 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as UUIDType


# revision identifiers, used by Alembic.
revision: str = 'create_meeting_tasks'
down_revision: Union[str, None] = 'add_weeek_api_token_to_staff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create MeetingTasks table (idempotent — checks existence first)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "MeetingTasks" in inspector.get_table_names():
        return

    op.create_table(
        'MeetingTasks',
        sa.Column('id', UUIDType(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), index=True, nullable=False),
        sa.Column('summary_id', UUIDType(as_uuid=True), sa.ForeignKey('Summaries.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('assignee', sa.Text, nullable=False, server_default=''),
        sa.Column('deadline', sa.Text, nullable=False, server_default=''),
        sa.Column('sent_to_crm', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('crm_task_id', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Drop MeetingTasks table."""
    op.drop_table('MeetingTasks')
