from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class SearchEntityType(StrEnum):
    MATTER = "matter"
    CLIENT = "client"
    DOCUMENT = "document"
    FACT = "fact"
    EVIDENCE = "evidence"
    WITNESS = "witness"
    CONTRACT = "contract"
    DRAFT = "draft"
    DEADLINE = "deadline"
    HEARING = "hearing"
    TASK = "task"
    INVOICE = "invoice"
    STATUTE = "statute"
    JUDGMENT = "judgment"
    PRECEDENT = "precedent"
    COMMUNICATION = "communication"


class SearchPreference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_preferences"
    __table_args__ = (UniqueConstraint("membership_id", name="uq_search_preferences_membership"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    default_scopes_json: Mapped[list] = mapped_column(JSON, default=list)
    default_language: Mapped[str] = mapped_column(String(20), default="bilingual")
    max_results: Mapped[int] = mapped_column(Integer, default=30)
    include_legal_corpus: Mapped[bool] = mapped_column(Boolean, default=True)
    show_recent_items: Mapped[bool] = mapped_column(Boolean, default=True)
    command_palette_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SavedSearch(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_searches"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    query: Mapped[str] = mapped_column(Text)
    scopes_json: Mapped[list] = mapped_column(JSON, default=list)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecentItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "recent_items"
    __table_args__ = (
        UniqueConstraint("membership_id", "entity_type", "entity_id", name="uq_recent_item_membership_entity"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[SearchEntityType] = mapped_column(String(40), index=True)
    entity_id: Mapped[UUID] = mapped_column(index=True)
    title_snapshot: Mapped[str] = mapped_column(String(500))
    subtitle_snapshot: Mapped[str | None] = mapped_column(String(700))
    href: Mapped[str] = mapped_column(String(1000))
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open_count: Mapped[int] = mapped_column(Integer, default=1)
