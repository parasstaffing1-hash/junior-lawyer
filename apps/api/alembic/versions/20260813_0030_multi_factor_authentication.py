"""multi-factor authentication credentials

`security_users.mfa_enrolled` already existed as a flag with nothing behind it.
These two tables are what it now reflects: one enrolled authenticator per user,
plus single-use recovery codes stored as hashes.

Revision ID: 20260813_0030
Revises: 20260812_0029
Create Date: 2026-08-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '20260813_0030'
down_revision: Union[str, None] = '20260812_0029'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_mfa_credentials',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('secret', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False, server_default='Authenticator app'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_counter', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['security_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_mfa_credential_user'),
    )
    op.create_index(op.f('ix_user_mfa_credentials_user_id'), 'user_mfa_credentials', ['user_id'])
    op.create_index(op.f('ix_user_mfa_credentials_confirmed_at'), 'user_mfa_credentials', ['confirmed_at'])

    op.create_table(
        'user_recovery_codes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['security_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_recovery_codes_user_id'), 'user_recovery_codes', ['user_id'])
    op.create_index(op.f('ix_user_recovery_codes_code_hash'), 'user_recovery_codes', ['code_hash'])


def downgrade() -> None:
    op.drop_index(op.f('ix_user_recovery_codes_code_hash'), table_name='user_recovery_codes')
    op.drop_index(op.f('ix_user_recovery_codes_user_id'), table_name='user_recovery_codes')
    op.drop_table('user_recovery_codes')
    op.drop_index(op.f('ix_user_mfa_credentials_confirmed_at'), table_name='user_mfa_credentials')
    op.drop_index(op.f('ix_user_mfa_credentials_user_id'), table_name='user_mfa_credentials')
    op.drop_table('user_mfa_credentials')
