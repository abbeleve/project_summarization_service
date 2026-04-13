"""add model preference columns to scheduled_meetings

Revision ID: 2026_meeting_models
Revises: 2026_scheduled_meetings
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_meeting_models'
down_revision = '2026_scheduled_meetings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('scheduled_meetings', sa.Column('transcribe_model', sa.String(50), nullable=True))
    op.add_column('scheduled_meetings', sa.Column('diarization_model', sa.String(100), nullable=True))
    op.add_column('scheduled_meetings', sa.Column('diarize_lib', sa.String(20), nullable=True))
    op.add_column('scheduled_meetings', sa.Column('transcribe_lib', sa.String(20), nullable=True))
    op.add_column('scheduled_meetings', sa.Column('llm_model', sa.String(50), nullable=True))
    op.add_column('scheduled_meetings', sa.Column('noise_suppression', sa.Boolean(), nullable=True))

    # Set defaults for existing записей
    op.execute("""
        UPDATE scheduled_meetings SET
            transcribe_model = 'v3_ctc',
            diarization_model = 'pyannote/speaker-diarization-community-1',
            diarize_lib = 'pyannote',
            transcribe_lib = 'gigaam',
            llm_model = 'gemini-2.5-flash',
            noise_suppression = false
        WHERE transcribe_model IS NULL
    """)


def downgrade() -> None:
    op.drop_column('scheduled_meetings', 'noise_suppression')
    op.drop_column('scheduled_meetings', 'llm_model')
    op.drop_column('scheduled_meetings', 'transcribe_lib')
    op.drop_column('scheduled_meetings', 'diarize_lib')
    op.drop_column('scheduled_meetings', 'diarization_model')
    op.drop_column('scheduled_meetings', 'transcribe_model')
