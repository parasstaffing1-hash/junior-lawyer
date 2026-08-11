"""Counterparty contract review, playbooks and deterministic redlining.

Revision ID: 20260808_0005
Revises: 20260808_0004
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0005"
down_revision: Union[str, None] = "20260808_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

contract_type = sa.Enum(
    "NDA", "EMPLOYMENT", "CONSULTING", "FREELANCE", "VENDOR", "SERVICES", "SAAS", "SOFTWARE_DEVELOPMENT",
    name="contracttype", native_enum=False,
)
risk_profile = sa.Enum("BALANCED", "PRO_PARTY_A", "PRO_PARTY_B", name="contractriskprofile", native_enum=False)
risk_level = sa.Enum("LOW", "MEDIUM", "HIGH", name="contractrisklevel", native_enum=False)
review_format = sa.Enum("DOCX", "PDF", "TXT", name="reviewsourceformat", native_enum=False)
review_status = sa.Enum("UPLOADED", "ANALYZED", "IN_NEGOTIATION", "APPROVED", "ARCHIVED", name="contractreviewstatus", native_enum=False)
deviation_status = sa.Enum("MATCHED", "MODIFIED", "UNKNOWN", name="clausedeviationstatus", native_enum=False)
finding_status = sa.Enum("OPEN", "RESOLVED", "ACCEPTED", "IGNORED", name="reviewfindingstatus", native_enum=False)
requirement = sa.Enum("REQUIRED", "OPTIONAL", "PROHIBITED", name="playbookrequirement", native_enum=False)
redline_status = sa.Enum("GENERATED", "SUPERSEDED", name="redlinestatus", native_enum=False)


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "contract_playbooks",
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("owner_label", sa.String(length=240), nullable=False),
        sa.Column("contract_type", contract_type, nullable=False),
        sa.Column("risk_profile", risk_profile, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_playbooks")),
        sa.UniqueConstraint("name", "contract_type", name="uq_contract_playbook_name_type"),
    )
    for column in ("name", "contract_type", "risk_profile", "active"):
        op.create_index(op.f(f"ix_contract_playbooks_{column}"), "contract_playbooks", [column], unique=False)

    op.create_table(
        "contract_playbook_rules",
        sa.Column("playbook_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=180), nullable=False),
        sa.Column("clause_type", sa.String(length=120), nullable=False),
        sa.Column("requirement", requirement, nullable=False),
        sa.Column("preferred_variant", sa.String(length=80), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("guidance_en", sa.Text(), nullable=False),
        sa.Column("guidance_hi", sa.Text(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["playbook_id"], ["contract_playbooks.id"], name=op.f("fk_contract_playbook_rules_playbook_id_contract_playbooks"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_playbook_rules")),
        sa.UniqueConstraint("playbook_id", "code", name="uq_contract_playbook_rule_code"),
    )
    for column in ("playbook_id", "code", "clause_type", "requirement", "risk_level"):
        op.create_index(op.f(f"ix_contract_playbook_rules_{column}"), "contract_playbook_rules", [column], unique=False)

    op.create_table(
        "counterparty_contract_reviews",
        sa.Column("matter_id", sa.Uuid(), nullable=True),
        sa.Column("internal_contract_id", sa.Uuid(), nullable=True),
        sa.Column("playbook_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=350), nullable=False),
        sa.Column("counterparty_name", sa.String(length=300), nullable=True),
        sa.Column("contract_type", contract_type, nullable=False),
        sa.Column("status", review_status, nullable=False),
        sa.Column("source_format", review_format, nullable=False),
        sa.Column("source_filename", sa.String(length=350), nullable=False),
        sa.Column("source_storage_key", sa.String(length=900), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=30), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("text_length", sa.Integer(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_counterparty_contract_reviews_matter_id_matters"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["internal_contract_id"], ["contracts.id"], name=op.f("fk_counterparty_contract_reviews_internal_contract_id_contracts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["playbook_id"], ["contract_playbooks.id"], name=op.f("fk_counterparty_contract_reviews_playbook_id_contract_playbooks"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_counterparty_contract_reviews")),
    )
    for column in ("matter_id", "internal_contract_id", "playbook_id", "title", "counterparty_name", "contract_type", "status", "source_format", "source_sha256", "language"):
        op.create_index(op.f(f"ix_counterparty_contract_reviews_{column}"), "counterparty_contract_reviews", [column], unique=False)

    op.create_table(
        "counterparty_review_clauses",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("clause_type", sa.String(length=120), nullable=False),
        sa.Column("heading", sa.String(length=350), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("classification_confidence", sa.Float(), nullable=False),
        sa.Column("matched_template_id", sa.Uuid(), nullable=True),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("deviation_status", deviation_status, nullable=False),
        sa.Column("suggested_title_en", sa.String(length=300), nullable=True),
        sa.Column("suggested_title_hi", sa.String(length=300), nullable=True),
        sa.Column("suggested_body_en", sa.Text(), nullable=True),
        sa.Column("suggested_body_hi", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["review_id"], ["counterparty_contract_reviews.id"], name=op.f("fk_counterparty_review_clauses_review_id_counterparty_contract_reviews"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_template_id"], ["clause_templates.id"], name=op.f("fk_counterparty_review_clauses_matched_template_id_clause_templates"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_counterparty_review_clauses")),
        sa.UniqueConstraint("review_id", "position", name="uq_counterparty_review_clause_position"),
    )
    for column in ("review_id", "clause_type", "position", "matched_template_id", "deviation_status", "decision"):
        op.create_index(op.f(f"ix_counterparty_review_clauses_{column}"), "counterparty_review_clauses", [column], unique=False)

    op.create_table(
        "counterparty_review_findings",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("review_clause_id", sa.Uuid(), nullable=True),
        sa.Column("rule_code", sa.String(length=220), nullable=False),
        sa.Column("clause_type", sa.String(length=120), nullable=True),
        sa.Column("title", sa.String(length=350), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("level", risk_level, nullable=False),
        sa.Column("status", finding_status, nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["review_id"], ["counterparty_contract_reviews.id"], name=op.f("fk_counterparty_review_findings_review_id_counterparty_contract_reviews"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_clause_id"], ["counterparty_review_clauses.id"], name=op.f("fk_counterparty_review_findings_review_clause_id_counterparty_review_clauses"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_counterparty_review_findings")),
        sa.UniqueConstraint("review_id", "rule_code", name="uq_counterparty_review_finding_rule"),
    )
    for column in ("review_id", "review_clause_id", "rule_code", "clause_type", "level", "status"):
        op.create_index(op.f(f"ix_counterparty_review_findings_{column}"), "counterparty_review_findings", [column], unique=False)

    op.create_table(
        "contract_redline_versions",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("status", redline_status, nullable=False),
        sa.Column("changes_json", sa.JSON(), nullable=False),
        sa.Column("generated_filename", sa.String(length=350), nullable=False),
        sa.Column("generated_storage_key", sa.String(length=900), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["review_id"], ["counterparty_contract_reviews.id"], name=op.f("fk_contract_redline_versions_review_id_counterparty_contract_reviews"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_redline_versions")),
        sa.UniqueConstraint("review_id", "version_number", name="uq_contract_redline_version"),
    )
    for column in ("review_id", "version_number", "status", "sha256"):
        op.create_index(op.f(f"ix_contract_redline_versions_{column}"), "contract_redline_versions", [column], unique=False)


def downgrade() -> None:
    op.drop_table("contract_redline_versions")
    op.drop_table("counterparty_review_findings")
    op.drop_table("counterparty_review_clauses")
    op.drop_table("counterparty_contract_reviews")
    op.drop_table("contract_playbook_rules")
    op.drop_table("contract_playbooks")
