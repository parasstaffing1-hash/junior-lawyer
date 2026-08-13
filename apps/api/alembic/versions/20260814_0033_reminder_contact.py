"""phone number for diary reminders

WhatsApp needs a number to send to. Optional, because a lawyer who wants the
diary by email only never provides one.

Revision ID: 20260814_0033
Revises: 20260813_0032
Create Date: 2026-08-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '20260814_0033'
down_revision: Union[str, None] = '20260813_0032'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('security_users', sa.Column('phone_e164', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('security_users', 'phone_e164')
