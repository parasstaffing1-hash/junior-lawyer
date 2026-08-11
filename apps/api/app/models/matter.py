from enum import StrEnum

from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class MatterStatus(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MatterLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    BILINGUAL = "bilingual"


class Matter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matters"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300), index=True)
    reference_number: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    client_name: Mapped[str | None] = mapped_column(String(250), index=True)
    court_name: Mapped[str | None] = mapped_column(String(300))
    case_number: Mapped[str | None] = mapped_column(String(150), index=True)
    cnr_number: Mapped[str | None] = mapped_column(String(32), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(100), default="India")
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[MatterStatus] = mapped_column(
        Enum(MatterStatus, native_enum=False), default=MatterStatus.ACTIVE, index=True
    )
    primary_language: Mapped[MatterLanguage] = mapped_column(
        Enum(MatterLanguage, native_enum=False), default=MatterLanguage.BILINGUAL
    )

    documents = relationship(
        "Document",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    facts = relationship(
        "MatterFact",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    timeline_events = relationship(
        "TimelineEvent",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    statements = relationship(
        "MatterStatement",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    contradictions = relationship(
        "MatterContradiction",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    review_items = relationship(
        "ReviewItem",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    contracts = relationship(
        "Contract",
        back_populates="matter",
        lazy="selectin",
    )
    legal_drafts = relationship(
        "LegalDraft",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    procedures = relationship(
        "MatterProcedure",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    deadlines = relationship(
        "MatterDeadline",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    hearings = relationship(
        "Hearing",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
