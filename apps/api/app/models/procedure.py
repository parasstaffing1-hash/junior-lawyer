from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ProcedurePackStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class DayBasis(StrEnum):
    CALENDAR = "calendar"
    BUSINESS = "business"


class DeadlineAdjustment(StrEnum):
    NONE = "none"
    NEXT_WORKING_DAY = "next_working_day"
    PREVIOUS_WORKING_DAY = "previous_working_day"


class MatterProcedureStatus(StrEnum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    COMPLETED = "completed"
    CLOSED = "closed"


class ComplianceStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAIVED = "waived"


class DeadlineStatus(StrEnum):
    UPCOMING = "upcoming"
    DUE_TODAY = "due_today"
    OVERDUE = "overdue"
    COMPLETED = "completed"
    REVIEW = "review"


class HearingStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    ADJOURNED = "adjourned"
    CANCELLED = "cancelled"


class DirectionStatus(StrEnum):
    OPEN = "open"
    COMPLIED = "complied"
    WAIVED = "waived"


class ProcedurePack(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "procedure_packs"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_procedure_packs_code_version"),)

    code: Mapped[str] = mapped_column(String(180), index=True)
    name_en: Mapped[str] = mapped_column(String(300))
    name_hi: Mapped[str | None] = mapped_column(String(300))
    jurisdiction: Mapped[str] = mapped_column(String(120), default="India", index=True)
    proceeding_type: Mapped[str] = mapped_column(String(160), index=True)
    court_level: Mapped[str | None] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    status: Mapped[ProcedurePackStatus] = mapped_column(
        Enum(ProcedurePackStatus, native_enum=False), default=ProcedurePackStatus.DRAFT, index=True
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source_name: Mapped[str | None] = mapped_column(String(350))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_citation: Mapped[str | None] = mapped_column(String(500))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    steps = relationship("ProcedureStep", back_populates="pack", cascade="all, delete-orphan", lazy="selectin", order_by="ProcedureStep.sequence")
    deadline_rules = relationship("DeadlineRule", back_populates="pack", cascade="all, delete-orphan", lazy="selectin")


class ProcedureStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "procedure_steps"
    __table_args__ = (UniqueConstraint("pack_id", "code", name="uq_procedure_steps_pack_code"),)

    pack_id: Mapped[UUID] = mapped_column(ForeignKey("procedure_packs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(180), index=True)
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    name_en: Mapped[str] = mapped_column(String(300))
    name_hi: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    dependency_codes_json: Mapped[list] = mapped_column(JSON, default=list)
    checklist_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    pack = relationship("ProcedurePack", back_populates="steps")


class DeadlineRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deadline_rules"
    __table_args__ = (UniqueConstraint("pack_id", "code", name="uq_deadline_rules_pack_code"),)

    pack_id: Mapped[UUID] = mapped_column(ForeignKey("procedure_packs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(180), index=True)
    name_en: Mapped[str] = mapped_column(String(300))
    name_hi: Mapped[str | None] = mapped_column(String(300))
    trigger_code: Mapped[str] = mapped_column(String(180), index=True)
    offset_days: Mapped[int] = mapped_column(Integer)
    day_basis: Mapped[DayBasis] = mapped_column(Enum(DayBasis, native_enum=False), default=DayBasis.CALENDAR)
    count_from_next_day: Mapped[bool] = mapped_column(Boolean, default=True)
    adjustment: Mapped[DeadlineAdjustment] = mapped_column(
        Enum(DeadlineAdjustment, native_enum=False), default=DeadlineAdjustment.NONE
    )
    requires_lawyer_review: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source_name: Mapped[str | None] = mapped_column(String(350))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_citation: Mapped[str | None] = mapped_column(String(500))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    pack = relationship("ProcedurePack", back_populates="deadline_rules")


class MatterProcedure(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_procedures"

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    pack_id: Mapped[UUID] = mapped_column(ForeignKey("procedure_packs.id", ondelete="RESTRICT"), index=True)
    status: Mapped[MatterProcedureStatus] = mapped_column(
        Enum(MatterProcedureStatus, native_enum=False), default=MatterProcedureStatus.ACTIVE, index=True
    )
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    pack_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    matter = relationship("Matter", back_populates="procedures")
    pack = relationship("ProcedurePack")
    compliances = relationship("MatterCompliance", back_populates="matter_procedure", cascade="all, delete-orphan", lazy="selectin")
    deadlines = relationship("MatterDeadline", back_populates="matter_procedure", cascade="all, delete-orphan", lazy="selectin")


class MatterCompliance(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_compliances"

    matter_procedure_id: Mapped[UUID] = mapped_column(ForeignKey("matter_procedures.id", ondelete="CASCADE"), index=True)
    procedure_step_id: Mapped[UUID | None] = mapped_column(ForeignKey("procedure_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(350))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, native_enum=False), default=ComplianceStatus.PENDING, index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(250))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter_procedure = relationship("MatterProcedure", back_populates="compliances")
    procedure_step = relationship("ProcedureStep")


class MatterDeadline(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_deadlines"

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    matter_procedure_id: Mapped[UUID | None] = mapped_column(ForeignKey("matter_procedures.id", ondelete="CASCADE"), nullable=True, index=True)
    deadline_rule_id: Mapped[UUID | None] = mapped_column(ForeignKey("deadline_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(350))
    trigger_type: Mapped[str] = mapped_column(String(120), default="manual", index=True)
    trigger_id: Mapped[str | None] = mapped_column(String(100), index=True)
    trigger_date: Mapped[date] = mapped_column(Date, index=True)
    calculated_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[DeadlineStatus] = mapped_column(
        Enum(DeadlineStatus, native_enum=False), default=DeadlineStatus.REVIEW, index=True
    )
    reviewed_by_lawyer: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calculation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    authority_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    matter = relationship("Matter", back_populates="deadlines")
    matter_procedure = relationship("MatterProcedure", back_populates="deadlines")
    deadline_rule = relationship("DeadlineRule")


class Hearing(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hearings"

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    court_name: Mapped[str | None] = mapped_column(String(350))
    courtroom: Mapped[str | None] = mapped_column(String(180))
    judge_or_bench: Mapped[str | None] = mapped_column(String(350))
    purpose: Mapped[str | None] = mapped_column(String(350))
    status: Mapped[HearingStatus] = mapped_column(
        Enum(HearingStatus, native_enum=False), default=HearingStatus.SCHEDULED, index=True
    )
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter = relationship("Matter", back_populates="hearings")
    directions = relationship("HearingDirection", back_populates="hearing", cascade="all, delete-orphan", lazy="selectin", order_by="HearingDirection.created_at")


class HearingDirection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hearing_directions"

    hearing_id: Mapped[UUID] = mapped_column(ForeignKey("hearings.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[DirectionStatus] = mapped_column(
        Enum(DirectionStatus, native_enum=False), default=DirectionStatus.OPEN, index=True
    )
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    extracted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=100)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    hearing = relationship("Hearing", back_populates="directions")
