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
    parties = relationship(
        "MatterParty",
        back_populates="matter",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MatterParty.name",
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


class PartyRole(StrEnum):
    """Where a party stands in the matter, not who they are to the firm."""

    CLIENT = "client"
    OPPOSING = "opposing"
    CO_PARTY = "co_party"
    THIRD_PARTY = "third_party"
    COURT = "court"
    REGULATOR = "regulator"
    WITNESS = "witness"


class PartyKind(StrEnum):
    INDIVIDUAL = "individual"
    COMPANY = "company"
    GOVERNMENT = "government"
    OTHER = "other"


class MatterParty(Base, UUIDMixin, TimestampMixin):
    """A named party on a matter, including the other side.

    Conflict checking already stored counterparties as loose JSON on a check
    record; this makes them first-class so opposing parties can be searched,
    linked to evidence, and screened against future intake.
    """

    __tablename__ = "matter_parties"

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[PartyRole] = mapped_column(Enum(PartyRole, native_enum=False), index=True)
    kind: Mapped[PartyKind] = mapped_column(
        Enum(PartyKind, native_enum=False), default=PartyKind.INDIVIDUAL
    )
    name: Mapped[str] = mapped_column(String(300), index=True)
    # Case-folded, whitespace-collapsed name, so conflict screening can match
    # "M/s ABC Pvt. Ltd." against "abc pvt ltd" without scanning every row.
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    representing_firm: Mapped[str | None] = mapped_column(String(300))
    advocate_name: Mapped[str | None] = mapped_column(String(250))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(60))
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    matter = relationship("Matter", back_populates="parties")
