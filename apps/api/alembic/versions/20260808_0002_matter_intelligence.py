"""Deterministic facts, chronology, evidence, contradictions, and review queue.

Revision ID: 20260808_0002
Revises: 20260808_0001
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0002"
down_revision: Union[str, None] = "20260808_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

fact_type = sa.Enum("DATE", "MONEY", "IDENTIFIER", "TEXT", name="facttype", native_enum=False)
fact_status = sa.Enum("AUTO", "CONFIRMED", "REJECTED", name="factstatus", native_enum=False)
source_relation = sa.Enum("SUPPORTS", "CONTRADICTS", "CONTEXT", name="sourcerelation", native_enum=False)
statement_kind = sa.Enum("CLAIM", "ADMISSION", "DENIAL", name="statementkind", native_enum=False)
contradiction_severity = sa.Enum("LOW", "MEDIUM", "HIGH", name="contradictionseverity", native_enum=False)
contradiction_status = sa.Enum("OPEN", "RESOLVED", "DISMISSED", name="contradictionstatus", native_enum=False)
review_item_type = sa.Enum("FACT", "CONTRADICTION", "STATEMENT", name="reviewitemtype", native_enum=False)
review_priority = sa.Enum("LOW", "MEDIUM", "HIGH", name="reviewpriority", native_enum=False)
review_status = sa.Enum("OPEN", "CONFIRMED", "REJECTED", "DISMISSED", name="reviewstatus", native_enum=False)


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "matter_facts",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("fact_key", sa.String(length=220), nullable=False),
        sa.Column("fact_type", fact_type, nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=220), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", fact_status, nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_matter_facts_matter_id_matters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matter_facts")),
        sa.UniqueConstraint("matter_id", "fact_key", "normalized_value", name="uq_matter_facts_key_value"),
    )
    for column in ("matter_id", "fact_key", "fact_type", "category", "normalized_value", "status"):
        op.create_index(op.f(f"ix_matter_facts_{column}"), "matter_facts", [column], unique=False)

    op.create_table(
        "fact_sources",
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("relation", source_relation, nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=True),
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["fact_id"], ["matter_facts.id"], name=op.f("fk_fact_sources_fact_id_matter_facts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_fact_sources_document_id_documents"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"], name=op.f("fk_fact_sources_page_id_document_pages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fact_sources")),
    )
    for column in ("fact_id", "document_id", "page_id", "page_number"):
        op.create_index(op.f(f"ix_fact_sources_{column}"), "fact_sources", [column], unique=False)

    op.create_table(
        "timeline_events",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=500), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_timeline_events_matter_id_matters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_timeline_events")),
        sa.UniqueConstraint("matter_id", "event_key", name="uq_timeline_events_matter_event_key"),
    )
    for column in ("matter_id", "event_key", "event_type", "event_date"):
        op.create_index(op.f(f"ix_timeline_events_{column}"), "timeline_events", [column], unique=False)

    op.create_table(
        "timeline_event_sources",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=True),
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["event_id"], ["timeline_events.id"], name=op.f("fk_timeline_event_sources_event_id_timeline_events"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_timeline_event_sources_document_id_documents"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"], name=op.f("fk_timeline_event_sources_page_id_document_pages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_timeline_event_sources")),
    )
    for column in ("event_id", "document_id", "page_id", "page_number"):
        op.create_index(op.f(f"ix_timeline_event_sources_{column}"), "timeline_event_sources", [column], unique=False)

    op.create_table(
        "matter_statements",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("kind", statement_kind, nullable=False),
        sa.Column("speaker_role", sa.String(length=100), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=True),
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_matter_statements_matter_id_matters"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_matter_statements_document_id_documents"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"], name=op.f("fk_matter_statements_page_id_document_pages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matter_statements")),
    )
    for column in ("matter_id", "document_id", "page_id", "page_number", "kind", "speaker_role"):
        op.create_index(op.f(f"ix_matter_statements_{column}"), "matter_statements", [column], unique=False)

    op.create_table(
        "matter_contradictions",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("contradiction_key", sa.String(length=300), nullable=False),
        sa.Column("fact_key", sa.String(length=220), nullable=False),
        sa.Column("label", sa.String(length=250), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("severity", contradiction_severity, nullable=False),
        sa.Column("status", contradiction_status, nullable=False),
        sa.Column("values_json", sa.JSON(), nullable=False),
        sa.Column("fact_ids_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_matter_contradictions_matter_id_matters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matter_contradictions")),
        sa.UniqueConstraint("matter_id", "contradiction_key", name="uq_matter_contradictions_key"),
    )
    for column in ("matter_id", "contradiction_key", "fact_key", "severity", "status"):
        op.create_index(op.f(f"ix_matter_contradictions_{column}"), "matter_contradictions", [column], unique=False)

    op.create_table(
        "review_items",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("item_type", review_item_type, nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("priority", review_priority, nullable=False),
        sa.Column("status", review_status, nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_review_items_matter_id_matters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_items")),
    )
    for column in ("matter_id", "item_type", "target_id", "priority", "status"):
        op.create_index(op.f(f"ix_review_items_{column}"), "review_items", [column], unique=False)


def downgrade() -> None:
    op.drop_table("review_items")
    op.drop_table("matter_contradictions")
    op.drop_table("matter_statements")
    op.drop_table("timeline_event_sources")
    op.drop_table("timeline_events")
    op.drop_table("fact_sources")
    op.drop_table("matter_facts")
