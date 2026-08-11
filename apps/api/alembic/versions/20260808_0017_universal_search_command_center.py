"""universal search and command center

Revision ID: 20260808_0017
Revises: 20260808_0016
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0017"
down_revision: Union[str, None] = "20260808_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_preferences",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("default_scopes_json", sa.JSON(), nullable=False),
        sa.Column("default_language", sa.String(length=20), nullable=False),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("include_legal_corpus", sa.Boolean(), nullable=False),
        sa.Column("show_recent_items", sa.Boolean(), nullable=False),
        sa.Column("command_palette_enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["organization_memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership_id", name="uq_search_preferences_membership"),
    )
    op.create_index(op.f("ix_search_preferences_membership_id"), "search_preferences", ["membership_id"], unique=False)
    op.create_index(op.f("ix_search_preferences_organization_id"), "search_preferences", ["organization_id"], unique=False)

    op.create_table(
        "saved_searches",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["organization_memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_saved_searches_membership_id"), "saved_searches", ["membership_id"], unique=False)
    op.create_index(op.f("ix_saved_searches_name"), "saved_searches", ["name"], unique=False)
    op.create_index(op.f("ix_saved_searches_organization_id"), "saved_searches", ["organization_id"], unique=False)
    op.create_index(op.f("ix_saved_searches_pinned"), "saved_searches", ["pinned"], unique=False)

    op.create_table(
        "recent_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("title_snapshot", sa.String(length=500), nullable=False),
        sa.Column("subtitle_snapshot", sa.String(length=700), nullable=True),
        sa.Column("href", sa.String(length=1000), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=True),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["organization_memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership_id", "entity_type", "entity_id", name="uq_recent_item_membership_entity"),
    )
    for column in ["organization_id", "membership_id", "entity_type", "entity_id", "matter_id", "client_id", "opened_at"]:
        op.create_index(op.f(f"ix_recent_items_{column}"), "recent_items", [column], unique=False)


def downgrade() -> None:
    op.drop_table("recent_items")
    op.drop_table("saved_searches")
    op.drop_table("search_preferences")
