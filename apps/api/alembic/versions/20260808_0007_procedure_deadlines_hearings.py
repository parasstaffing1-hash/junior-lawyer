"""Procedure packs, deadline calculations, compliance and hearings.

Revision ID: 20260808_0007
Revises: 20260808_0006
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0007"
down_revision: Union[str, None] = "20260808_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

pack_status = sa.Enum("DRAFT", "ACTIVE", "DEPRECATED", name="procedurepackstatus", native_enum=False)
day_basis = sa.Enum("CALENDAR", "BUSINESS", name="daybasis", native_enum=False)
adjustment = sa.Enum("NONE", "NEXT_WORKING_DAY", "PREVIOUS_WORKING_DAY", name="deadlineadjustment", native_enum=False)
procedure_status = sa.Enum("NOT_STARTED", "ACTIVE", "COMPLETED", "CLOSED", name="matterprocedurestatus", native_enum=False)
compliance_status = sa.Enum("PENDING", "IN_PROGRESS", "COMPLETED", "WAIVED", name="compliancestatus", native_enum=False)
deadline_status = sa.Enum("UPCOMING", "DUE_TODAY", "OVERDUE", "COMPLETED", "REVIEW", name="deadlinestatus", native_enum=False)
hearing_status = sa.Enum("SCHEDULED", "COMPLETED", "ADJOURNED", "CANCELLED", name="hearingstatus", native_enum=False)
direction_status = sa.Enum("OPEN", "COMPLIED", "WAIVED", name="directionstatus", native_enum=False)


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
        "procedure_packs",
        sa.Column("code", sa.String(length=180), nullable=False),
        sa.Column("name_en", sa.String(length=300), nullable=False),
        sa.Column("name_hi", sa.String(length=300), nullable=True),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("proceeding_type", sa.String(length=160), nullable=False),
        sa.Column("court_level", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", pack_status, nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_name", sa.String(length=350), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_citation", sa.String(length=500), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_procedure_packs")),
        sa.UniqueConstraint("code", "version", name="uq_procedure_packs_code_version"),
    )
    add_indexes("procedure_packs", ["code", "jurisdiction", "proceeding_type", "court_level", "version", "status", "effective_from", "effective_to", "verified"])

    op.create_table(
        "procedure_steps",
        sa.Column("pack_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=180), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name_en", sa.String(length=300), nullable=False),
        sa.Column("name_hi", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("dependency_codes_json", sa.JSON(), nullable=False),
        sa.Column("checklist_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["pack_id"], ["procedure_packs.id"], name=op.f("fk_procedure_steps_pack_id_procedure_packs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_procedure_steps")),
        sa.UniqueConstraint("pack_id", "code", name="uq_procedure_steps_pack_code"),
    )
    add_indexes("procedure_steps", ["pack_id", "code", "sequence", "required"])

    op.create_table(
        "deadline_rules",
        sa.Column("pack_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=180), nullable=False),
        sa.Column("name_en", sa.String(length=300), nullable=False),
        sa.Column("name_hi", sa.String(length=300), nullable=True),
        sa.Column("trigger_code", sa.String(length=180), nullable=False),
        sa.Column("offset_days", sa.Integer(), nullable=False),
        sa.Column("day_basis", day_basis, nullable=False),
        sa.Column("count_from_next_day", sa.Boolean(), nullable=False),
        sa.Column("adjustment", adjustment, nullable=False),
        sa.Column("requires_lawyer_review", sa.Boolean(), nullable=False),
        sa.Column("source_name", sa.String(length=350), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_citation", sa.String(length=500), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["pack_id"], ["procedure_packs.id"], name=op.f("fk_deadline_rules_pack_id_procedure_packs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deadline_rules")),
        sa.UniqueConstraint("pack_id", "code", name="uq_deadline_rules_pack_code"),
    )
    add_indexes("deadline_rules", ["pack_id", "code", "trigger_code", "requires_lawyer_review", "verified"])

    op.create_table(
        "matter_procedures",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("pack_id", sa.Uuid(), nullable=False),
        sa.Column("status", procedure_status, nullable=False),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("pack_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_matter_procedures_matter_id_matters"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pack_id"], ["procedure_packs.id"], name=op.f("fk_matter_procedures_pack_id_procedure_packs"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matter_procedures")),
    )
    add_indexes("matter_procedures", ["matter_id", "pack_id", "status"])

    op.create_table(
        "matter_compliances",
        sa.Column("matter_procedure_id", sa.Uuid(), nullable=False),
        sa.Column("procedure_step_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=350), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", compliance_status, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("assigned_to", sa.String(length=250), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_procedure_id"], ["matter_procedures.id"], name=op.f("fk_matter_compliances_matter_procedure_id_matter_procedures"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["procedure_step_id"], ["procedure_steps.id"], name=op.f("fk_matter_compliances_procedure_step_id_procedure_steps"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], name=op.f("fk_matter_compliances_source_document_id_documents"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matter_compliances")),
    )
    add_indexes("matter_compliances", ["matter_procedure_id", "procedure_step_id", "status", "due_date", "source_document_id"])

    op.create_table(
        "matter_deadlines",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("matter_procedure_id", sa.Uuid(), nullable=True),
        sa.Column("deadline_rule_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=350), nullable=False),
        sa.Column("trigger_type", sa.String(length=120), nullable=False),
        sa.Column("trigger_id", sa.String(length=100), nullable=True),
        sa.Column("trigger_date", sa.Date(), nullable=False),
        sa.Column("calculated_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", deadline_status, nullable=False),
        sa.Column("reviewed_by_lawyer", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculation_json", sa.JSON(), nullable=False),
        sa.Column("authority_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_matter_deadlines_matter_id_matters"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matter_procedure_id"], ["matter_procedures.id"], name=op.f("fk_matter_deadlines_matter_procedure_id_matter_procedures"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deadline_rule_id"], ["deadline_rules.id"], name=op.f("fk_matter_deadlines_deadline_rule_id_deadline_rules"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matter_deadlines")),
    )
    add_indexes("matter_deadlines", ["matter_id", "matter_procedure_id", "deadline_rule_id", "trigger_type", "trigger_id", "trigger_date", "calculated_date", "due_date", "status", "reviewed_by_lawyer"])

    op.create_table(
        "hearings",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("court_name", sa.String(length=350), nullable=True),
        sa.Column("courtroom", sa.String(length=180), nullable=True),
        sa.Column("judge_or_bench", sa.String(length=350), nullable=True),
        sa.Column("purpose", sa.String(length=350), nullable=True),
        sa.Column("status", hearing_status, nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_hearings_matter_id_matters"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], name=op.f("fk_hearings_source_document_id_documents"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hearings")),
    )
    add_indexes("hearings", ["matter_id", "scheduled_for", "status", "source_document_id"])

    op.create_table(
        "hearing_directions",
        sa.Column("hearing_id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", direction_status, nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("extracted", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("requires_review", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["hearing_id"], ["hearings.id"], name=op.f("fk_hearing_directions_hearing_id_hearings"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_hearing_directions_matter_id_matters"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], name=op.f("fk_hearing_directions_source_document_id_documents"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hearing_directions")),
    )
    add_indexes("hearing_directions", ["hearing_id", "matter_id", "due_date", "status", "source_document_id", "extracted", "requires_review"])


def downgrade() -> None:
    op.drop_table("hearing_directions")
    op.drop_table("hearings")
    op.drop_table("matter_deadlines")
    op.drop_table("matter_compliances")
    op.drop_table("matter_procedures")
    op.drop_table("deadline_rules")
    op.drop_table("procedure_steps")
    op.drop_table("procedure_packs")
