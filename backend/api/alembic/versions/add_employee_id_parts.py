"""add employee_id to PartsTranscription

Revision ID: add_employee_id_parts
Revises: e5f6g7h8i9j0
Create Date: 2026-05-22 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'add_employee_id_parts'
down_revision: Union[str, None] = 'add_recording_url'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'PartsTranscription',
        sa.Column(
            'employee_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('Staff.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        )
    )


def downgrade() -> None:
    op.drop_column('PartsTranscription', 'employee_id')
