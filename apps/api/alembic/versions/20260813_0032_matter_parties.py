"""matter parties

Opposing parties existed only as loose JSON on a conflict-check record, so
they could not be searched, corrected, or screened against later intake. This
makes every party on a matter a row, with a normalized name to screen on.

Revision ID: 20260813_0032
Revises: 20260813_0031
Create Date: 2026-08-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


party_role = sa.Enum(
    "CLIENT", "OPPOSING", "CO_PARTY", "THIRD_PARTY", "COURT", "REGULATOR", "WITNESS",
    name="partyrole", native_enum=False,
)
party_kind = sa.Enum(
    "INDIVIDUAL", "COMPANY", "GOVERNMENT", "OTHER", name="partykind", native_enum=False
)

revision: str = '20260813_0032'
down_revision: Union[str, None] = '20260813_0031'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'matter_parties',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('matter_id', sa.Uuid(), nullable=False),
        sa.Column('role', party_role, nullable=False),
        sa.Column('kind', party_kind, nullable=False, server_default='INDIVIDUAL'),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('normalized_name', sa.String(length=300), nullable=False),
        sa.Column('client_id', sa.Uuid(), nullable=True),
        sa.Column('representing_firm', sa.String(length=300), nullable=True),
        sa.Column('advocate_name', sa.String(length=250), nullable=True),
        sa.Column('contact_email', sa.String(length=320), nullable=True),
        sa.Column('contact_phone', sa.String(length=60), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['matter_id'], ['matters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_matter_parties_matter_id'), 'matter_parties', ['matter_id'])
    op.create_index(op.f('ix_matter_parties_role'), 'matter_parties', ['role'])
    op.create_index(op.f('ix_matter_parties_name'), 'matter_parties', ['name'])
    op.create_index(op.f('ix_matter_parties_normalized_name'), 'matter_parties', ['normalized_name'])
    op.create_index(op.f('ix_matter_parties_client_id'), 'matter_parties', ['client_id'])
    op.create_index(op.f('ix_matter_parties_is_active'), 'matter_parties', ['is_active'])


def downgrade() -> None:
    op.drop_index(op.f('ix_matter_parties_is_active'), table_name='matter_parties')
    op.drop_index(op.f('ix_matter_parties_client_id'), table_name='matter_parties')
    op.drop_index(op.f('ix_matter_parties_normalized_name'), table_name='matter_parties')
    op.drop_index(op.f('ix_matter_parties_name'), table_name='matter_parties')
    op.drop_index(op.f('ix_matter_parties_role'), table_name='matter_parties')
    op.drop_index(op.f('ix_matter_parties_matter_id'), table_name='matter_parties')
    op.drop_table('matter_parties')
