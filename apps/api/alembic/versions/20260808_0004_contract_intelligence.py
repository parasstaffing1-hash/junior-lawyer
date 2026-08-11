"""Contract intelligence, clause library, risks and versions.

Revision ID: 20260808_0004
Revises: 20260808_0003
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0004"
down_revision: Union[str, None] = "20260808_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

contract_type = sa.Enum(
    "NDA", "EMPLOYMENT", "CONSULTING", "FREELANCE", "VENDOR", "SERVICES", "SAAS", "SOFTWARE_DEVELOPMENT",
    name="contracttype", native_enum=False,
)
contract_language = sa.Enum("ENGLISH", "HINDI", "BILINGUAL", name="contractlanguage", native_enum=False)
contract_status = sa.Enum("DRAFT", "IN_REVIEW", "APPROVED", "SUPERSEDED", name="contractstatus", native_enum=False)
risk_profile = sa.Enum("BALANCED", "PRO_PARTY_A", "PRO_PARTY_B", name="contractriskprofile", native_enum=False)
risk_level = sa.Enum("LOW", "MEDIUM", "HIGH", name="contractrisklevel", native_enum=False)
risk_status = sa.Enum("OPEN", "RESOLVED", "IGNORED", name="contractriskstatus", native_enum=False)
clause_source = sa.Enum("BUILTIN", "CUSTOM", name="clausesource", native_enum=False)


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "clause_templates",
        sa.Column("code", sa.String(length=180), nullable=False),
        sa.Column("clause_type", sa.String(length=120), nullable=False),
        sa.Column("variant_key", sa.String(length=80), nullable=False),
        sa.Column("title_en", sa.String(length=300), nullable=False),
        sa.Column("title_hi", sa.String(length=300), nullable=True),
        sa.Column("body_en", sa.Text(), nullable=False),
        sa.Column("body_hi", sa.Text(), nullable=True),
        sa.Column("contract_types_json", sa.JSON(), nullable=False),
        sa.Column("variables_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clause_templates")),
        sa.UniqueConstraint("code", "version", name="uq_clause_templates_code_version"),
    )
    for column in ("code", "clause_type", "variant_key", "version", "active"):
        op.create_index(op.f(f"ix_clause_templates_{column}"), "clause_templates", [column], unique=False)

    op.create_table(
        "contracts",
        sa.Column("matter_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=350), nullable=False),
        sa.Column("contract_type", contract_type, nullable=False),
        sa.Column("language", contract_language, nullable=False),
        sa.Column("status", contract_status, nullable=False),
        sa.Column("risk_profile", risk_profile, nullable=False),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("governing_state", sa.String(length=120), nullable=True),
        sa.Column("party_a_name", sa.String(length=300), nullable=False),
        sa.Column("party_b_name", sa.String(length=300), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("questionnaire_json", sa.JSON(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("generated_filename", sa.String(length=350), nullable=True),
        sa.Column("generated_storage_key", sa.String(length=900), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_contracts_matter_id_matters"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contracts")),
    )
    for column in ("matter_id", "title", "contract_type", "language", "status", "risk_profile", "jurisdiction", "governing_state", "party_a_name", "party_b_name", "effective_date"):
        op.create_index(op.f(f"ix_contracts_{column}"), "contracts", [column], unique=False)

    op.create_table(
        "contract_clauses",
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("clause_template_id", sa.Uuid(), nullable=True),
        sa.Column("clause_code", sa.String(length=180), nullable=False),
        sa.Column("clause_type", sa.String(length=120), nullable=False),
        sa.Column("variant_key", sa.String(length=80), nullable=False),
        sa.Column("title_en", sa.String(length=300), nullable=False),
        sa.Column("title_hi", sa.String(length=300), nullable=True),
        sa.Column("body_en", sa.Text(), nullable=False),
        sa.Column("body_hi", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source", clause_source, nullable=False),
        sa.Column("is_modified", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], name=op.f("fk_contract_clauses_contract_id_contracts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clause_template_id"], ["clause_templates.id"], name=op.f("fk_contract_clauses_clause_template_id_clause_templates"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_clauses")),
        sa.UniqueConstraint("contract_id", "position", name="uq_contract_clauses_position"),
    )
    for column in ("contract_id", "clause_template_id", "clause_code", "clause_type", "variant_key", "position", "source", "is_modified"):
        op.create_index(op.f(f"ix_contract_clauses_{column}"), "contract_clauses", [column], unique=False)

    op.create_table(
        "contract_risks",
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.String(length=180), nullable=False),
        sa.Column("clause_type", sa.String(length=120), nullable=True),
        sa.Column("title", sa.String(length=320), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("level", risk_level, nullable=False),
        sa.Column("status", risk_status, nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], name=op.f("fk_contract_risks_contract_id_contracts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_risks")),
        sa.UniqueConstraint("contract_id", "rule_code", name="uq_contract_risks_rule"),
    )
    for column in ("contract_id", "rule_code", "clause_type", "level", "status"):
        op.create_index(op.f(f"ix_contract_risks_{column}"), "contract_risks", [column], unique=False)

    op.create_table(
        "contract_versions",
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("questionnaire_json", sa.JSON(), nullable=False),
        sa.Column("clauses_json", sa.JSON(), nullable=False),
        sa.Column("risks_json", sa.JSON(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("generated_filename", sa.String(length=350), nullable=True),
        sa.Column("generated_storage_key", sa.String(length=900), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], name=op.f("fk_contract_versions_contract_id_contracts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_versions")),
        sa.UniqueConstraint("contract_id", "version_number", name="uq_contract_versions_number"),
    )
    for column in ("contract_id", "version_number", "sha256"):
        op.create_index(op.f(f"ix_contract_versions_{column}"), "contract_versions", [column], unique=False)


def downgrade() -> None:
    op.drop_table("contract_versions")
    op.drop_table("contract_risks")
    op.drop_table("contract_clauses")
    op.drop_table("contracts")
    op.drop_table("clause_templates")
