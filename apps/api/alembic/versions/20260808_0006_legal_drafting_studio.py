"""Legal drafting studio with provenance, review findings and immutable versions.

Revision ID: 20260808_0006
Revises: 20260808_0005
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0006"
down_revision: Union[str, None] = "20260808_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


draft_type = sa.Enum(
    "LEGAL_NOTICE", "NOTICE_REPLY", "AFFIDAVIT", "APPLICATION", "PETITION",
    "WRITTEN_STATEMENT", "REJOINDER", "WRITTEN_SUBMISSIONS", "CHRONOLOGY",
    "ANNEXURE_INDEX", "CASE_SYNOPSIS", "HEARING_NOTE",
    name="legaldrafttype", native_enum=False,
)
draft_language = sa.Enum("ENGLISH", "HINDI", "BILINGUAL", name="legaldraftlanguage", native_enum=False)
draft_status = sa.Enum("DRAFT", "IN_REVIEW", "APPROVED", "SUPERSEDED", name="legaldraftstatus", native_enum=False)
section_source = sa.Enum("DETERMINISTIC", "MANUAL", "AI", name="draftsectionsource", native_enum=False)
source_type = sa.Enum(
    "FACT", "TIMELINE", "DOCUMENT", "STATEMENT", "CONTRADICTION",
    "STATUTE_SECTION", "JUDGMENT_PARAGRAPH", "MANUAL",
    name="draftsourcetype", native_enum=False,
)
finding_level = sa.Enum("LOW", "MEDIUM", "HIGH", name="draftfindinglevel", native_enum=False)
finding_status = sa.Enum("OPEN", "RESOLVED", "ACCEPTED", name="draftfindingstatus", native_enum=False)


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def add_indexes(table: str, columns: list[str]) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def upgrade() -> None:
    op.create_table(
        "legal_draft_templates",
        sa.Column("code", sa.String(length=160), nullable=False),
        sa.Column("draft_type", draft_type, nullable=False),
        sa.Column("name_en", sa.String(length=250), nullable=False),
        sa.Column("name_hi", sa.String(length=250), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("structure_json", sa.JSON(), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_draft_templates")),
        sa.UniqueConstraint("code", "version", name="uq_legal_draft_templates_code_version"),
    )
    add_indexes("legal_draft_templates", ["code", "draft_type", "version", "active"])

    op.create_table(
        "legal_drafts",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=400), nullable=False),
        sa.Column("draft_type", draft_type, nullable=False),
        sa.Column("language", draft_language, nullable=False),
        sa.Column("status", draft_status, nullable=False),
        sa.Column("court_name", sa.String(length=350), nullable=True),
        sa.Column("case_number", sa.String(length=180), nullable=True),
        sa.Column("questionnaire_json", sa.JSON(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("generated_filename", sa.String(length=400), nullable=True),
        sa.Column("generated_storage_key", sa.String(length=900), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_legal_drafts_matter_id_matters"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["legal_draft_templates.id"], name=op.f("fk_legal_drafts_template_id_legal_draft_templates"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_drafts")),
    )
    add_indexes("legal_drafts", ["matter_id", "template_id", "title", "draft_type", "language", "status", "case_number"])

    op.create_table(
        "legal_draft_sections",
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("section_key", sa.String(length=160), nullable=False),
        sa.Column("title_en", sa.String(length=350), nullable=False),
        sa.Column("title_hi", sa.String(length=350), nullable=True),
        sa.Column("body_en", sa.Text(), nullable=False),
        sa.Column("body_hi", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source", section_source, nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["draft_id"], ["legal_drafts.id"], name=op.f("fk_legal_draft_sections_draft_id_legal_drafts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_draft_sections")),
        sa.UniqueConstraint("draft_id", "position", name="uq_legal_draft_sections_position"),
    )
    add_indexes("legal_draft_sections", ["draft_id", "section_key", "position", "source", "reviewed", "locked"])

    op.create_table(
        "legal_draft_sources",
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("locator", sa.String(length=300), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["draft_id"], ["legal_drafts.id"], name=op.f("fk_legal_draft_sources_draft_id_legal_drafts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["legal_draft_sections.id"], name=op.f("fk_legal_draft_sources_section_id_legal_draft_sections"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_draft_sources")),
    )
    add_indexes("legal_draft_sources", ["draft_id", "section_id", "source_type", "source_id", "verified"])

    op.create_table(
        "legal_draft_findings",
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.String(length=180), nullable=False),
        sa.Column("section_key", sa.String(length=160), nullable=True),
        sa.Column("title", sa.String(length=350), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("level", finding_level, nullable=False),
        sa.Column("status", finding_status, nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["draft_id"], ["legal_drafts.id"], name=op.f("fk_legal_draft_findings_draft_id_legal_drafts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_draft_findings")),
        sa.UniqueConstraint("draft_id", "rule_code", name="uq_legal_draft_findings_rule"),
    )
    add_indexes("legal_draft_findings", ["draft_id", "rule_code", "section_key", "level", "status"])

    op.create_table(
        "legal_draft_versions",
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("sections_json", sa.JSON(), nullable=False),
        sa.Column("findings_json", sa.JSON(), nullable=False),
        sa.Column("sources_json", sa.JSON(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("generated_filename", sa.String(length=400), nullable=True),
        sa.Column("generated_storage_key", sa.String(length=900), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["draft_id"], ["legal_drafts.id"], name=op.f("fk_legal_draft_versions_draft_id_legal_drafts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_draft_versions")),
        sa.UniqueConstraint("draft_id", "version_number", name="uq_legal_draft_versions_number"),
    )
    add_indexes("legal_draft_versions", ["draft_id", "version_number", "sha256"])


def downgrade() -> None:
    op.drop_table("legal_draft_versions")
    op.drop_table("legal_draft_findings")
    op.drop_table("legal_draft_sources")
    op.drop_table("legal_draft_sections")
    op.drop_table("legal_drafts")
    op.drop_table("legal_draft_templates")
