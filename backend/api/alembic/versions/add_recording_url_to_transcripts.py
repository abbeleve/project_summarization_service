"""add_recording_url_to_transcripts

Revision ID: add_recording_url
Revises: de1c6a0a98e7
Create Date: 2026-05-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_recording_url'
down_revision: Union[str, Sequence[str], None] = 'de1c6a0a98e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('Transcripts', sa.Column('recording_url', sa.Text(), nullable=True,
                  comment='URL аудиофайла в MinIO/S3 для воспроизведения в плеере'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('Transcripts', 'recording_url')
