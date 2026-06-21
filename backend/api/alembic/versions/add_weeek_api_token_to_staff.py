"""add weeek_api_token to Staff for CRM integration

Revision ID: add_weeek_api_token_to_staff
Revises: add_tasks_to_summaries
Create Date: 2026-06-21 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_weeek_api_token_to_staff'
down_revision: Union[str, None] = 'add_tasks_to_summaries'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add weeek_api_token column to Staff table."""
    op.add_column(
        'Staff',
        sa.Column(
            'weeek_api_token',
            sa.Text,
            nullable=True,
            comment='Зашифрованный API токен Weeek для интеграции CRM'
        )
    )


def downgrade() -> None:
    """Drop weeek_api_token column from Staff table."""
    op.drop_column('Staff', 'weeek_api_token')
