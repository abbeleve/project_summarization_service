"""add pipeline column to scheduled_meetings for pipeline selection

Revision ID: add_pipeline_col
Revises: remove_tasks_from_summaries
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_pipeline_col'
down_revision: Union[str, None] = 'remove_tasks_from_summaries'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'scheduled_meetings'
                AND column_name = 'pipeline'
            ) THEN
                ALTER TABLE scheduled_meetings
                ADD COLUMN pipeline VARCHAR(20) DEFAULT 'whisperx';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE scheduled_meetings
        DROP COLUMN IF EXISTS pipeline;
        """
    )
