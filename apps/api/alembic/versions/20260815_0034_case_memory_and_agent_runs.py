"""case memory and agent runs

Case memory gives a matter one standing record of the lawyer's reading of it —
issues, open questions, strategy — alongside a derived snapshot of the facts,
timeline and contradictions that already persist elsewhere.

Agent runs sequence existing engines into one piece of work and stop at the
lawyer. Deterministic steps run with AI switched off; AI steps point back at
ai_runs so verification is not duplicated.

Revision ID: 20260815_0034
Revises: 20260814_0033
Create Date: 2026-08-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '20260815_0034'
down_revision: Union[str, None] = '20260814_0033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'matter_memory',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('matter_id', sa.Uuid(), nullable=False),
        sa.Column('issues_json', sa.JSON(), nullable=False),
        sa.Column('open_questions_json', sa.JSON(), nullable=False),
        sa.Column('strategy_notes', sa.Text(), nullable=True),
        sa.Column('snapshot_json', sa.JSON(), nullable=False),
        sa.Column('refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['matter_id'], ['matters.id'], name=op.f('fk_matter_memory_matter_id_matters'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_matter_memory')),
    )
    op.create_index(op.f('ix_matter_memory_matter_id'), 'matter_memory', ['matter_id'], unique=True)

    op.create_table(
        'agent_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('matter_id', sa.Uuid(), nullable=False),
        sa.Column('recipe', sa.String(length=40), nullable=False),
        sa.Column('title', sa.String(length=250), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('output_language', sa.String(length=20), nullable=False),
        sa.Column('summary_json', sa.JSON(), nullable=False),
        sa.Column('ai_available', sa.Boolean(), nullable=False),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.String(length=250), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['matter_id'], ['matters.id'], name=op.f('fk_agent_runs_matter_id_matters'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_runs')),
    )
    op.create_index(op.f('ix_agent_runs_matter_id'), 'agent_runs', ['matter_id'])
    op.create_index(op.f('ix_agent_runs_recipe'), 'agent_runs', ['recipe'])
    op.create_index(op.f('ix_agent_runs_status'), 'agent_runs', ['status'])

    op.create_table(
        'agent_steps',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('step_key', sa.String(length=80), nullable=False),
        sa.Column('label', sa.String(length=250), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('output_json', sa.JSON(), nullable=False),
        sa.Column('ai_run_id', sa.Uuid(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], name=op.f('fk_agent_steps_run_id_agent_runs'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ai_run_id'], ['ai_runs.id'], name=op.f('fk_agent_steps_ai_run_id_ai_runs'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_steps')),
    )
    op.create_index(op.f('ix_agent_steps_run_id'), 'agent_steps', ['run_id'])
    op.create_index(op.f('ix_agent_steps_ordinal'), 'agent_steps', ['ordinal'])
    op.create_index(op.f('ix_agent_steps_step_key'), 'agent_steps', ['step_key'])
    op.create_index(op.f('ix_agent_steps_kind'), 'agent_steps', ['kind'])
    op.create_index(op.f('ix_agent_steps_status'), 'agent_steps', ['status'])
    op.create_index(op.f('ix_agent_steps_ai_run_id'), 'agent_steps', ['ai_run_id'])


def downgrade() -> None:
    op.drop_table('agent_steps')
    op.drop_table('agent_runs')
    op.drop_index(op.f('ix_matter_memory_matter_id'), table_name='matter_memory')
    op.drop_table('matter_memory')
