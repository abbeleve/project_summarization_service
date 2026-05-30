"""create_annotations_table

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-01-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as UUIDType

# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('Annotations',
        sa.Column('id', UUIDType(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('part_id', UUIDType(as_uuid=True), sa.ForeignKey('PartsTranscription.id', ondelete='CASCADE'), nullable=False),
        sa.Column('employee_id', UUIDType(as_uuid=True), sa.ForeignKey('Staff.id', ondelete='CASCADE'), nullable=False),
        sa.Column('start_char', sa.Integer(), nullable=False),
        sa.Column('end_char', sa.Integer(), nullable=False),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.CheckConstraint('end_char > start_char'),
    )
    
    op.create_index('ix_annotations_part_id', 'Annotations', ['part_id'])
    op.create_index('ix_annotations_employee_id', 'Annotations', ['employee_id'])
    
    print("✅ Таблица Annotations создана")


def downgrade():
    op.drop_table('Annotations')
    print("✅ Таблица Annotations удалена")
