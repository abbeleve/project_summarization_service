"""remove_employee_id_from_parts_transcription

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-01-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as UUIDType

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade():
    # Удаляем колонку employee_id (вместе с foreign key)
    op.drop_column('PartsTranscription', 'employee_id')
    
    print("✅ employee_id удалён из PartsTranscription")


def downgrade():
    # Возвращаем колонку employee_id
    op.add_column('PartsTranscription',
        sa.Column('employee_id', UUIDType(as_uuid=True), nullable=True)
    )
    
    # Заполняем на основе транскрипций
    op.execute("""
        UPDATE "PartsTranscription" pt
        SET employee_id = (
            SELECT t.employee_id 
            FROM "Transcripts" t 
            WHERE t.id = pt.transcript_id
        )
    """)
    
    # Восстанавливаем foreign key
    op.create_foreign_key(
        'parts_transcription_employee_id_fkey',
        'PartsTranscription',
        'Staff',
        ['employee_id'],
        ['id'],
        ondelete='SET NULL'
    )
    
    print("✅ employee_id восстановлен в PartsTranscription")
