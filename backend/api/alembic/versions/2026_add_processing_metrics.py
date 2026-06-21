"""add ProcessingMetrics table for analytics

Revision ID: add_processing_metrics
Revises: add_role_to_staff
Create Date: 2026-06-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'add_processing_metrics'
down_revision: Union[str, None] = 'add_role_to_staff'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'ProcessingMetrics' in inspector.get_table_names():
        return  # таблица уже создана через Base.metadata.create_all()

    op.create_table(
        'ProcessingMetrics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), index=True, nullable=False),
        sa.Column('transcript_id', UUID(as_uuid=True), sa.ForeignKey('Transcripts.id', ondelete='CASCADE'), nullable=False, index=True, comment='ID транскрипции'),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('Staff.id', ondelete='CASCADE'), nullable=False, index=True, comment='ID пользователя'),
        sa.Column('audio_duration_sec', sa.Float(), nullable=False, comment='Длительность аудио в секундах'),
        sa.Column('transcribe_lib', sa.String(20), nullable=False, comment='whisper или gigaam'),
        sa.Column('transcribe_model', sa.String(50), nullable=True, comment='Модель ASR'),
        sa.Column('processing_duration_ms', sa.Integer(), nullable=False, comment='Время ASR в мс'),
        sa.Column('diarize_lib', sa.String(50), nullable=True, comment='Библиотека диаризации'),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True, comment='Размер аудиофайла'),
        sa.Column('noise_suppression', sa.Boolean(), nullable=True, comment='Шумоподавление'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True, comment='Время создания'),
    )


def downgrade() -> None:
    op.drop_table('ProcessingMetrics')
