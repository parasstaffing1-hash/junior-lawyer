"""ux accessibility performance polish

Revision ID: 20260808_0026
Revises: 20260808_0025
Create Date: 2026-08-08 19:57:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0026"
down_revision: Union[str, None] = "20260808_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_experience_preferences",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("ui_language", sa.String(length=20), nullable=False),
        sa.Column("density", sa.String(length=20), nullable=False),
        sa.Column("contrast", sa.String(length=20), nullable=False),
        sa.Column("font_scale", sa.String(length=20), nullable=False),
        sa.Column("reduce_motion", sa.Boolean(), nullable=False),
        sa.Column("show_keyboard_hints", sa.Boolean(), nullable=False),
        sa.Column("document_page_window", sa.Integer(), nullable=False),
        sa.Column("document_text_zoom", sa.Integer(), nullable=False),
        sa.Column("remember_last_workspace", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_user_experience_preferences_organization_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["organization_memberships.id"], name=op.f("fk_user_experience_preferences_membership_id_organization_memberships"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_experience_preferences")),
        sa.UniqueConstraint("membership_id", name="uq_user_experience_preferences_membership"),
    )
    with op.batch_alter_table("user_experience_preferences") as batch_op:
        batch_op.create_index(batch_op.f("ix_user_experience_preferences_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_user_experience_preferences_membership_id"), ["membership_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_user_experience_preferences_ui_language"), ["ui_language"], unique=False)

    op.create_table(
        "user_onboarding_progress",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("completed_steps_json", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.String(length=80), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_user_onboarding_progress_organization_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["organization_memberships.id"], name=op.f("fk_user_onboarding_progress_membership_id_organization_memberships"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_onboarding_progress")),
        sa.UniqueConstraint("membership_id", name="uq_user_onboarding_progress_membership"),
    )
    with op.batch_alter_table("user_onboarding_progress") as batch_op:
        batch_op.create_index(batch_op.f("ix_user_onboarding_progress_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_user_onboarding_progress_membership_id"), ["membership_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_user_onboarding_progress_completed_at"), ["completed_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_user_onboarding_progress_dismissed_at"), ["dismissed_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("user_onboarding_progress") as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_onboarding_progress_dismissed_at"))
        batch_op.drop_index(batch_op.f("ix_user_onboarding_progress_completed_at"))
        batch_op.drop_index(batch_op.f("ix_user_onboarding_progress_membership_id"))
        batch_op.drop_index(batch_op.f("ix_user_onboarding_progress_organization_id"))
    op.drop_table("user_onboarding_progress")
    with op.batch_alter_table("user_experience_preferences") as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_experience_preferences_ui_language"))
        batch_op.drop_index(batch_op.f("ix_user_experience_preferences_membership_id"))
        batch_op.drop_index(batch_op.f("ix_user_experience_preferences_organization_id"))
    op.drop_table("user_experience_preferences")
