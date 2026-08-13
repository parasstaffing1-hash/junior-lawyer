"""AI conversation threads

The reasoning engine could only answer one-shot questions. These two tables
add continuity: a thread scoped to an organization (optionally to a matter),
and its turns. Assistant turns point at the AIRun that produced them, so
sources, claims, citations and verification stay where they already live.

Revision ID: 20260813_0031
Revises: 20260813_0030
Create Date: 2026-08-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


conversation_status = sa.Enum("ACTIVE", "ARCHIVED", name="conversationstatus", native_enum=False)
message_role = sa.Enum("USER", "ASSISTANT", name="conversationmessagerole", native_enum=False)

revision: str = '20260813_0031'
down_revision: Union[str, None] = '20260813_0030'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('matter_id', sa.Uuid(), nullable=True),
        sa.Column('title', sa.String(length=250), nullable=False),
        sa.Column('jurisdiction', sa.String(length=120), nullable=False, server_default='India'),
        sa.Column('output_language', sa.String(length=20), nullable=False, server_default='en'),
        sa.Column('status', conversation_status, nullable=False, server_default='ACTIVE'),
        sa.Column('document_ids_json', sa.JSON(), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['security_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['matter_id'], ['matters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_conversations_organization_id'), 'ai_conversations', ['organization_id'])
    op.create_index(op.f('ix_ai_conversations_created_by_user_id'), 'ai_conversations', ['created_by_user_id'])
    op.create_index(op.f('ix_ai_conversations_matter_id'), 'ai_conversations', ['matter_id'])
    op.create_index(op.f('ix_ai_conversations_jurisdiction'), 'ai_conversations', ['jurisdiction'])
    op.create_index(op.f('ix_ai_conversations_status'), 'ai_conversations', ['status'])
    op.create_index(op.f('ix_ai_conversations_last_message_at'), 'ai_conversations', ['last_message_at'])

    op.create_table(
        'ai_conversation_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('role', message_role, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=True),
        sa.Column('author_user_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['ai_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['author_user_id'], ['security_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id', 'ordinal', name='uq_conversation_message_ordinal'),
    )
    op.create_index(op.f('ix_ai_conversation_messages_conversation_id'), 'ai_conversation_messages', ['conversation_id'])
    op.create_index(op.f('ix_ai_conversation_messages_ordinal'), 'ai_conversation_messages', ['ordinal'])
    op.create_index(op.f('ix_ai_conversation_messages_role'), 'ai_conversation_messages', ['role'])
    op.create_index(op.f('ix_ai_conversation_messages_run_id'), 'ai_conversation_messages', ['run_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_conversation_messages_run_id'), table_name='ai_conversation_messages')
    op.drop_index(op.f('ix_ai_conversation_messages_role'), table_name='ai_conversation_messages')
    op.drop_index(op.f('ix_ai_conversation_messages_ordinal'), table_name='ai_conversation_messages')
    op.drop_index(op.f('ix_ai_conversation_messages_conversation_id'), table_name='ai_conversation_messages')
    op.drop_table('ai_conversation_messages')
    op.drop_index(op.f('ix_ai_conversations_last_message_at'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_status'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_jurisdiction'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_matter_id'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_created_by_user_id'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_organization_id'), table_name='ai_conversations')
    op.drop_table('ai_conversations')
