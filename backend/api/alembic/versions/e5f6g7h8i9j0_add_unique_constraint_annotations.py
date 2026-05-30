"""add_unique_constraint_annotations

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-01-04

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    # Сначала удаляем дубликаты, оставляя только одну аннотацию для каждого набора (part_id, start_char, end_char, employee_id)
    op.execute("""
        DELETE FROM "Annotations" a1 USING "Annotations" a2
        WHERE a1.id > a2.id
          AND a1.part_id = a2.part_id
          AND a1.start_char = a2.start_char
          AND a1.end_char = a2.end_char
          AND a1.employee_id = a2.employee_id
    """)
    
    # Добавляем уникальный индекс чтобы предотвратить дублирование аннотаций
    op.create_unique_constraint(
        'uq_annotations_part_start_end_employee',
        'Annotations',
        ['part_id', 'start_char', 'end_char', 'employee_id']
    )
    print("✅ Дубликаты удалены, уникальный индекс добавлен")


def downgrade():
    op.drop_constraint(
        'uq_annotations_part_start_end_employee',
        'Annotations',
        type_='unique'
    )
    print("✅ Уникальный индекс удалён из Annotations")
