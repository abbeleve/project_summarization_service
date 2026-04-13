"""add ml_task_id column to scheduled_meetings table

Revision ID: 2026_add_ml_task_id
Revises: 2026_scheduled_meetings
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_add_ml_task_id'
down_revision = '2026_meeting_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'scheduled_meetings',
        sa.Column('ml_task_id', sa.String(100), nullable=True, comment='ID задачи Celery для ML пайплайна (транскрибация)')
    )


def downgrade() -> None:
    op.drop_column('scheduled_meetings', 'ml_task_id')
