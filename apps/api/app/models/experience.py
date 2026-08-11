from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class UILanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    BILINGUAL = "bilingual"


class UIDensity(StrEnum):
    COMFORTABLE = "comfortable"
    COMPACT = "compact"


class UIContrast(StrEnum):
    STANDARD = "standard"
    HIGH = "high"


class UIFontScale(StrEnum):
    SMALL = "small"
    DEFAULT = "default"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


class UserExperiencePreference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_experience_preferences"
    __table_args__ = (UniqueConstraint("membership_id", name="uq_user_experience_preferences_membership"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    ui_language: Mapped[UILanguage] = mapped_column(String(20), default=UILanguage.ENGLISH, index=True)
    density: Mapped[UIDensity] = mapped_column(String(20), default=UIDensity.COMFORTABLE)
    contrast: Mapped[UIContrast] = mapped_column(String(20), default=UIContrast.STANDARD)
    font_scale: Mapped[UIFontScale] = mapped_column(String(20), default=UIFontScale.DEFAULT)
    reduce_motion: Mapped[bool] = mapped_column(Boolean, default=False)
    show_keyboard_hints: Mapped[bool] = mapped_column(Boolean, default=True)
    document_page_window: Mapped[int] = mapped_column(Integer, default=8)
    document_text_zoom: Mapped[int] = mapped_column(Integer, default=100)
    remember_last_workspace: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class UserOnboardingProgress(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_onboarding_progress"
    __table_args__ = (UniqueConstraint("membership_id", name="uq_user_onboarding_progress_membership"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    completed_steps_json: Mapped[list] = mapped_column(JSON, default=list)
    current_step: Mapped[str | None] = mapped_column(String(80), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
