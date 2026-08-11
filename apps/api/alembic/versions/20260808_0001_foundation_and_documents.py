"""Foundation matter and deterministic document engine.

Revision ID: 20260808_0001
Revises: None
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

matter_status = sa.Enum("ACTIVE", "ON_HOLD", "CLOSED", "ARCHIVED", name="matterstatus", native_enum=False)
matter_language = sa.Enum("ENGLISH", "HINDI", "BILINGUAL", name="matterlanguage", native_enum=False)
document_language = sa.Enum("ENGLISH", "HINDI", "MIXED", "HINGLISH", "UNKNOWN", name="documentlanguage", native_enum=False)
processing_status = sa.Enum("PENDING", "PROCESSING", "READY", "FAILED", name="processingstatus", native_enum=False)
extraction_method = sa.Enum(
    "NATIVE_PDF", "OCR", "MIXED_PDF", "DOCX", "TEXT", "IMAGE_OCR", "UNKNOWN",
    name="extractionmethod", native_enum=False,
)
entity_type = sa.Enum(
    "CNR_NUMBER", "CASE_NUMBER", "CASE_TITLE", "PARTY", "COURT", "JUDGE", "DATE",
    "ACT", "STATUTE_REFERENCE", "CITATION", name="entitytype", native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "matters",
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("client_name", sa.String(length=250), nullable=True),
        sa.Column("court_name", sa.String(length=300), nullable=True),
        sa.Column("case_number", sa.String(length=150), nullable=True),
        sa.Column("cnr_number", sa.String(length=32), nullable=True),
        sa.Column("jurisdiction", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", matter_status, nullable=False),
        sa.Column("primary_language", matter_language, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matters")),
        sa.UniqueConstraint("reference_number", name=op.f("uq_matters_reference_number")),
    )
    op.create_index(op.f("ix_matters_case_number"), "matters", ["case_number"], unique=False)
    op.create_index(op.f("ix_matters_client_name"), "matters", ["client_name"], unique=False)
    op.create_index(op.f("ix_matters_cnr_number"), "matters", ["cnr_number"], unique=False)
    op.create_index(op.f("ix_matters_reference_number"), "matters", ["reference_number"], unique=True)
    op.create_index(op.f("ix_matters_status"), "matters", ["status"], unique=False)
    op.create_index(op.f("ix_matters_title"), "matters", ["title"], unique=False)

    op.create_table(
        "documents",
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=True),
        sa.Column("file_extension", sa.String(length=20), nullable=True),
        sa.Column("mime_type", sa.String(length=150), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("storage_key", sa.String(length=1000), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("text_char_count", sa.Integer(), nullable=False),
        sa.Column("detected_language", document_language, nullable=False),
        sa.Column("extraction_method", extraction_method, nullable=False),
        sa.Column("is_scanned", sa.Boolean(), nullable=False),
        sa.Column("ocr_used", sa.Boolean(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_status", processing_status, nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], name=op.f("fk_documents_matter_id_matters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("matter_id", "sha256", name="uq_documents_matter_sha256"),
    )
    op.create_index(op.f("ix_documents_detected_language"), "documents", ["detected_language"], unique=False)
    op.create_index(op.f("ix_documents_file_extension"), "documents", ["file_extension"], unique=False)
    op.create_index(op.f("ix_documents_matter_id"), "documents", ["matter_id"], unique=False)
    op.create_index(op.f("ix_documents_processing_status"), "documents", ["processing_status"], unique=False)
    op.create_index(op.f("ix_documents_sha256"), "documents", ["sha256"], unique=False)

    op.create_table(
        "document_pages",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("detected_language", document_language, nullable=False),
        sa.Column("extraction_method", extraction_method, nullable=False),
        sa.Column("is_scanned", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_document_pages_document_id_documents"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_pages")),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
    )
    op.create_index(op.f("ix_document_pages_document_id"), "document_pages", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_pages_text_sha256"), "document_pages", ["text_sha256"], unique=False)

    op.create_table(
        "document_entities",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("entity_type", entity_type, nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=True),
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_document_entities_document_id_documents"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"], name=op.f("fk_document_entities_page_id_document_pages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_entities")),
    )
    op.create_index(op.f("ix_document_entities_document_id"), "document_entities", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_entities_entity_type"), "document_entities", ["entity_type"], unique=False)
    op.create_index(op.f("ix_document_entities_normalized_value"), "document_entities", ["normalized_value"], unique=False)
    op.create_index(op.f("ix_document_entities_page_id"), "document_entities", ["page_id"], unique=False)
    op.create_index(op.f("ix_document_entities_page_number"), "document_entities", ["page_number"], unique=False)


def downgrade() -> None:
    op.drop_table("document_entities")
    op.drop_table("document_pages")
    op.drop_table("documents")
    op.drop_table("matters")
