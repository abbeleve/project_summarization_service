"""add scheduled_meetings table

Revision ID: 2026_scheduled_meetings
Revises: e5f6g7h8i9j0_add_unique_constraint_annotations
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

# revision identifiers, used by Alembic.
revision = '2026_scheduled_meetings'
down_revision = 'e5f6g7h8i9j0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scheduled_meetings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('Staff.id', ondelete='CASCADE'), nullable=False),
        sa.Column('meeting_url', sa.Text, nullable=False),
        sa.Column('provider', sa.String(20), nullable=False, comment='google, microsoft, zoom'),
        sa.Column('bot_name', sa.String(100), nullable=True, default='Meeting Notetaker'),
        sa.Column('scheduled_at', TIMESTAMP(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending',
                  comment='pending, processing, recording, completed, failed, cancelled'),
        sa.Column('meeting_bot_task_id', sa.String(100), nullable=True),
        sa.Column('recording_url', sa.Text, nullable=True),
        sa.Column('result_transcript_id', UUID(as_uuid=True), nullable=True),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scheduled_meetings_user_id', 'scheduled_meetings', ['user_id'])
    op.create_index('ix_scheduled_meetings_scheduled_at', 'scheduled_meetings', ['scheduled_at'])


def downgrade() -> None:
    op.drop_index('ix_scheduled_meetings_scheduled_at', 'scheduled_meetings')
    op.drop_index('ix_scheduled_meetings_user_id', 'scheduled_meetings')
    op.drop_table('scheduled_meetings')
