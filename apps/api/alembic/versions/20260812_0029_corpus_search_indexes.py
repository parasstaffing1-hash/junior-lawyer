"""corpus search trigram indexes

Corpus search now filters on the text columns in SQL instead of pulling an
arbitrary slice of the corpus into Python. Those predicates are ILIKE
'%term%', which PostgreSQL can only serve from an index via pg_trgm, so the
GIN indexes are created here.

PostgreSQL only: SQLite (development) has no trigram index and does not need
one at development corpus sizes, so the migration is a no-op there.

Revision ID: 20260812_0029
Revises: 20260808_0028
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op


revision: str = '20260812_0029'
down_revision: Union[str, None] = '20260808_0028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = (
    ("ix_statute_sections_normalized_text_trgm", "statute_sections", "normalized_text"),
    ("ix_statute_sections_heading_en_trgm", "statute_sections", "heading_en"),
    ("ix_judgment_paragraphs_normalized_text_trgm", "judgment_paragraphs", "normalized_text"),
    ("ix_judgments_case_title_trgm", "judgments", "case_title"),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, table, column in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING gin ({column} gin_trgm_ops)")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, _table, _column in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    # pg_trgm is left installed: other objects may depend on it, and dropping an
    # extension is not a safe inverse of CREATE EXTENSION IF NOT EXISTS.
