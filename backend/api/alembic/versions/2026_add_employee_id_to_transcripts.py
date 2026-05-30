"""add_employee_id_to_transcripts

Revision ID: 2026_add_employee_id_to_transcripts
Revises: a1b2c3d4e5f6
Create Date: 2026-01-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from uuid import UUID

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку employee_id в таблицу Transcripts
    op.add_column('Transcripts', 
        sa.Column('employee_id', UUIDType(as_uuid=True), nullable=True)
    )
    
    # Заполняем существующие записи на основе PartsTranscription
    # Берём первого employee_id для каждой транскрипции
    op.execute("""
        UPDATE "Transcripts" t
        SET employee_id = (
            SELECT pt.employee_id 
            FROM "PartsTranscription" pt 
            WHERE pt.transcript_id = t.id 
            LIMIT 1
        )
    """)
    
    # Для записей без parts (если есть) - ставим NULL (оставляем как есть)
    # Теперь делаем колонку NOT NULL для будущих записей
    # Но сначала проверим, есть ли NULL
    op.execute("""
        UPDATE "Transcripts" SET employee_id = (SELECT id FROM "Staff" LIMIT 1)
        WHERE employee_id IS NULL
    """)
    
    # Делаем колонку NOT NULL
    op.alter_column('Transcripts', 'employee_id', nullable=False)
    
    # Добавляем индекс для быстрого поиска по пользователю
    op.create_index('ix_transcripts_employee_id', 'Transcripts', ['employee_id'])
    
    # Добавляем foreign key
    op.create_foreign_key(
        'fk_transcripts_employee_id',
        'Transcripts',
        'Staff',
        ['employee_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Удаляем foreign key и индекс
    op.drop_constraint('fk_transcripts_employee_id', 'Transcripts', type_='foreignkey')
    op.drop_index('ix_transcripts_employee_id', table_name='Transcripts')
    
    # Удаляем колонку
    op.drop_column('Transcripts', 'employee_id')
