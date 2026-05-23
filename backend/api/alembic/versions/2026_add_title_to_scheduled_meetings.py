"""add title column to scheduled_meetings table

Revision ID: 2026_add_title
Revises: add_employee_id_parts
Create Date: 2026-05-24

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_add_title'
down_revision = 'add_employee_id_parts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('scheduled_meetings', sa.Column('title', sa.String(200), nullable=True,
                  comment='Название совещания, задаётся пользователем'))


def downgrade() -> None:
    op.drop_column('scheduled_meetings', 'title')
