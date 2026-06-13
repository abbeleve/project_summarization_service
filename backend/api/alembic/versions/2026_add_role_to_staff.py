"""add role column to Staff table

Revision ID: add_role_to_staff
Revises: 2026_add_title
Create Date: 2026-06-13

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_role_to_staff'
down_revision: Union[str, None] = '2026_add_title'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        'Staff',
        sa.Column(
            'role',
            sa.String(20),
            nullable=False,
            server_default='user',
            comment='Роль пользователя: user или admin'
        )
    )


def downgrade() -> None:
    op.drop_column('Staff', 'role')
