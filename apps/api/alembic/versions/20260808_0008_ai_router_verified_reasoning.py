"""AI router, evidence-bounded reasoning, verification and usage audit.

Revision ID: 20260808_0008
Revises: 20260808_0007
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0008"
down_revision: Union[str, None] = "20260808_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ai_task = sa.Enum(
    "EXTRACT_ENTITIES", "SEARCH_CASES", "LOOKUP_STATUTE", "CALCULATE_DEADLINE",
    "BUILD_CHRONOLOGY", "COMPARE_DOCUMENTS", "VERIFY_CITATION", "MATTER_SUMMARY",
    "DOCUMENT_SUMMARY", "CLIENT_UPDATE", "RESEARCH_SYNTHESIS", "ISSUE_SPOTTING",
    "ARGUMENT_ANALYSIS", "COUNTERARGUMENT", "CUSTOM_DRAFTING", "CUSTOM_CLAUSE",
    "HEARING_QUESTIONS", name="aitasktype", native_enum=False,
)
ai_tier = sa.Enum("DETERMINISTIC", "LOCAL", "STRONG", "BLOCKED", name="airoutetier", native_enum=False)
ai_run_status = sa.Enum(
    "PREPARED", "RUNNING", "COMPLETED", "VERIFICATION_FAILED", "BLOCKED", "FAILED",
    name="airunstatus", native_enum=False,
)
ai_verify = sa.Enum("NOT_RUN", "PASSED", "WARNINGS", "FAILED", name="aiverificationstatus", native_enum=False)
ai_review = sa.Enum("PENDING", "REVIEWED", "REJECTED", name="aireviewstatus", native_enum=False)
ai_source = sa.Enum(
    "MATTER_FACT", "TIMELINE_EVENT", "STATEMENT", "CONTRADICTION", "DOCUMENT_PAGE",
    "STATUTE_SECTION", "JUDGMENT_PARAGRAPH", name="aisourcetype", native_enum=False,
)
ai_claim = sa.Enum(
    "SUPPORTED", "WEAK_SUPPORT", "UNCITED", "INVALID_SOURCE", "NON_SUBSTANTIVE",
    name="aiclaimstatus", native_enum=False,
)
ai_citation = sa.Enum("RESOLVED", "AMBIGUOUS", "UNRESOLVED", "UNPARSED", name="aicitationstatus", native_enum=False)


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
        "ai_runs",
        sa.Column("matter_id", sa.Uuid(), nullable=True),
        sa.Column("task_type", ai_task, nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("output_language", sa.String(length=20), nullable=False),
        sa.Column("route_tier", ai_tier, nullable=False),
        sa.Column("status", ai_run_status, nullable=False),
        sa.Column("provider_key", sa.String(length=80), nullable=True),
        sa.Column("model_name", sa.String(length=200), nullable=True),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=True),
        sa.Column("routing_json", sa.JSON(), nullable=False),
        sa.Column("retrieval_json", sa.JSON(), nullable=False),
        sa.Column("request_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("verification_status", ai_verify, nullable=False),
        sa.Column("verification_summary_json", sa.JSON(), nullable=False),
        sa.Column("review_status", ai_review, nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=250), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_ai_runs_matter_id_matters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_runs")),
    )
    add_indexes("ai_runs", ["matter_id", "task_type", "output_language", "route_tier", "status", "provider_key", "model_name", "verification_status", "review_status"])

    op.create_table(
        "ai_run_sources",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=20), nullable=False),
        sa.Column("source_type", ai_source, nullable=False),
        sa.Column("source_record_id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=700), nullable=False),
        sa.Column("locator", sa.String(length=400), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=1500), nullable=True),
        sa.Column("official", sa.Boolean(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], name=op.f("fk_ai_run_sources_run_id_ai_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_run_sources")),
        sa.UniqueConstraint("run_id", "source_key", name="uq_ai_run_source_key"),
    )
    add_indexes("ai_run_sources", ["run_id", "ordinal", "source_key", "source_type", "source_record_id", "official", "verified", "relevance_score"])

    op.create_table(
        "ai_run_claims",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("substantive", sa.Boolean(), nullable=False),
        sa.Column("cited_source_keys_json", sa.JSON(), nullable=False),
        sa.Column("support_score", sa.Float(), nullable=False),
        sa.Column("status", ai_claim, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], name=op.f("fk_ai_run_claims_run_id_ai_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_run_claims")),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_ai_run_claim_ordinal"),
    )
    add_indexes("ai_run_claims", ["run_id", "ordinal", "substantive", "status"])

    op.create_table(
        "ai_run_citations",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("raw_citation", sa.String(length=350), nullable=False),
        sa.Column("normalized_citation", sa.String(length=220), nullable=True),
        sa.Column("status", ai_citation, nullable=False),
        sa.Column("matched_judgment_id", sa.Uuid(), nullable=True),
        sa.Column("cited_source_keys_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], name=op.f("fk_ai_run_citations_run_id_ai_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_judgment_id"], ["judgments.id"], name=op.f("fk_ai_run_citations_matched_judgment_id_judgments"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_run_citations")),
    )
    add_indexes("ai_run_citations", ["run_id", "normalized_citation", "status", "matched_judgment_id"])

    op.create_table(
        "ai_usage_events",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("provider_reported_cost_microunits", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=12), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], name=op.f("fk_ai_usage_events_run_id_ai_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage_events")),
    )
    add_indexes("ai_usage_events", ["run_id", "provider_key", "model_name"])


def downgrade() -> None:
    op.drop_table("ai_usage_events")
    op.drop_table("ai_run_citations")
    op.drop_table("ai_run_claims")
    op.drop_table("ai_run_sources")
    op.drop_table("ai_runs")
