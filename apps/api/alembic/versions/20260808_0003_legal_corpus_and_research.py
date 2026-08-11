"""India legal corpus, judgments, paragraphs, and citation graph.

Revision ID: 20260808_0003
Revises: 20260808_0002
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0003"
down_revision: Union[str, None] = "20260808_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

source_kind = sa.Enum(
    "INDIA_CODE", "ECOURTS", "SUPREME_COURT", "HIGH_COURT", "TRIBUNAL", "MANUAL", "OTHER",
    name="legalsourcekind", native_enum=False,
)
access_mode = sa.Enum(
    "OFFICIAL_DOWNLOAD", "MANUAL_IMPORT", "API", "WEBPAGE",
    name="accessmode", native_enum=False,
)
corpus_language = sa.Enum(
    "ENGLISH", "HINDI", "MIXED", "OTHER",
    name="corpuslanguage", native_enum=False,
)
court_level = sa.Enum(
    "SUPREME_COURT", "HIGH_COURT", "APPELLATE_TRIBUNAL", "TRIBUNAL", "DISTRICT_COURT", "OTHER",
    name="courtlevel", native_enum=False,
)
citation_status = sa.Enum(
    "RESOLVED", "AMBIGUOUS", "UNRESOLVED",
    name="citationresolutionstatus", native_enum=False,
)


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "legal_sources",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("kind", source_kind, nullable=False),
        sa.Column("base_url", sa.String(length=1000), nullable=True),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False),
        sa.Column("access_mode", access_mode, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_sources")),
        sa.UniqueConstraint("code", name=op.f("uq_legal_sources_code")),
    )
    for column in ("code", "kind", "jurisdiction", "official", "enabled"):
        op.create_index(op.f(f"ix_legal_sources_{column}"), "legal_sources", [column], unique=False)

    op.create_table(
        "statutes",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=250), nullable=False),
        sa.Column("title_en", sa.String(length=500), nullable=False),
        sa.Column("title_hi", sa.String(length=500), nullable=True),
        sa.Column("short_title", sa.String(length=300), nullable=True),
        sa.Column("act_number", sa.String(length=80), nullable=True),
        sa.Column("act_year", sa.Integer(), nullable=True),
        sa.Column("enactment_date", sa.Date(), nullable=True),
        sa.Column("ministry", sa.String(length=250), nullable=True),
        sa.Column("department", sa.String(length=250), nullable=True),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.String(length=1500), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["source_id"], ["legal_sources.id"], name=op.f("fk_statutes_source_id_legal_sources"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_statutes")),
        sa.UniqueConstraint("source_id", "external_id", name="uq_statutes_source_external"),
    )
    for column in (
        "source_id", "external_id", "title_en", "title_hi", "short_title", "act_number", "act_year",
        "enactment_date", "ministry", "department", "jurisdiction", "state", "is_active", "source_hash",
    ):
        op.create_index(op.f(f"ix_statutes_{column}"), "statutes", [column], unique=False)

    op.create_table(
        "statute_sections",
        sa.Column("statute_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("section_key", sa.String(length=180), nullable=False),
        sa.Column("section_number", sa.String(length=80), nullable=False),
        sa.Column("provision_type", sa.String(length=60), nullable=False),
        sa.Column("heading_en", sa.String(length=600), nullable=True),
        sa.Column("heading_hi", sa.String(length=600), nullable=True),
        sa.Column("text_en", sa.Text(), nullable=True),
        sa.Column("text_hi", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("version_label", sa.String(length=150), nullable=True),
        sa.Column("source_url", sa.String(length=1500), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["statute_id"], ["statutes.id"], name=op.f("fk_statute_sections_statute_id_statutes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["statute_sections.id"], name=op.f("fk_statute_sections_parent_id_statute_sections"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_statute_sections")),
        sa.UniqueConstraint("statute_id", "section_key", name="uq_statute_sections_key"),
    )
    for column in (
        "statute_id", "parent_id", "section_key", "section_number", "provision_type", "sort_order",
        "effective_from", "effective_to", "source_hash",
    ):
        op.create_index(op.f(f"ix_statute_sections_{column}"), "statute_sections", [column], unique=False)

    op.create_table(
        "judgments",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=250), nullable=False),
        sa.Column("case_title", sa.String(length=700), nullable=False),
        sa.Column("case_number", sa.String(length=250), nullable=True),
        sa.Column("neutral_citation", sa.String(length=180), nullable=True),
        sa.Column("reported_citations_json", sa.JSON(), nullable=False),
        sa.Column("court_name", sa.String(length=350), nullable=False),
        sa.Column("court_level", court_level, nullable=False),
        sa.Column("jurisdiction", sa.String(length=150), nullable=False),
        sa.Column("decision_date", sa.Date(), nullable=True),
        sa.Column("judges_json", sa.JSON(), nullable=False),
        sa.Column("bench_strength", sa.Integer(), nullable=True),
        sa.Column("acts_json", sa.JSON(), nullable=False),
        sa.Column("sections_json", sa.JSON(), nullable=False),
        sa.Column("language", corpus_language, nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=1500), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["source_id"], ["legal_sources.id"], name=op.f("fk_judgments_source_id_legal_sources"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judgments")),
        sa.UniqueConstraint("source_id", "external_id", name="uq_judgments_source_external"),
    )
    for column in (
        "source_id", "external_id", "case_title", "case_number", "neutral_citation", "court_name", "court_level",
        "jurisdiction", "decision_date", "bench_strength", "language", "source_hash",
    ):
        op.create_index(op.f(f"ix_judgments_{column}"), "judgments", [column], unique=False)

    op.create_table(
        "judgment_paragraphs",
        sa.Column("judgment_id", sa.Uuid(), nullable=False),
        sa.Column("paragraph_number", sa.String(length=60), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("language", corpus_language, nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["judgment_id"], ["judgments.id"], name=op.f("fk_judgment_paragraphs_judgment_id_judgments"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judgment_paragraphs")),
        sa.UniqueConstraint("judgment_id", "position", name="uq_judgment_paragraph_position"),
    )
    for column in ("judgment_id", "paragraph_number", "position", "language"):
        op.create_index(op.f(f"ix_judgment_paragraphs_{column}"), "judgment_paragraphs", [column], unique=False)

    op.create_table(
        "judgment_citations",
        sa.Column("citing_judgment_id", sa.Uuid(), nullable=False),
        sa.Column("paragraph_id", sa.Uuid(), nullable=True),
        sa.Column("cited_judgment_id", sa.Uuid(), nullable=True),
        sa.Column("raw_citation", sa.String(length=350), nullable=False),
        sa.Column("normalized_citation", sa.String(length=220), nullable=False),
        sa.Column("status", citation_status, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["citing_judgment_id"], ["judgments.id"], name=op.f("fk_judgment_citations_citing_judgment_id_judgments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paragraph_id"], ["judgment_paragraphs.id"], name=op.f("fk_judgment_citations_paragraph_id_judgment_paragraphs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cited_judgment_id"], ["judgments.id"], name=op.f("fk_judgment_citations_cited_judgment_id_judgments"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judgment_citations")),
        sa.UniqueConstraint("citing_judgment_id", "paragraph_id", "normalized_citation", name="uq_judgment_citation_occurrence"),
    )
    for column in ("citing_judgment_id", "paragraph_id", "cited_judgment_id", "normalized_citation", "status"):
        op.create_index(op.f(f"ix_judgment_citations_{column}"), "judgment_citations", [column], unique=False)


def downgrade() -> None:
    op.drop_table("judgment_citations")
    op.drop_table("judgment_paragraphs")
    op.drop_table("judgments")
    op.drop_table("statute_sections")
    op.drop_table("statutes")
    op.drop_table("legal_sources")
