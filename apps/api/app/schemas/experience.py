from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.experience import UIContrast, UIDensity, UIFontScale, UILanguage


class ExperiencePreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ui_language: UILanguage
    density: UIDensity
    contrast: UIContrast
    font_scale: UIFontScale
    reduce_motion: bool
    show_keyboard_hints: bool
    document_page_window: int
    document_text_zoom: int
    remember_last_workspace: bool
    metadata_json: dict
    updated_at: datetime


class ExperiencePreferenceUpdate(BaseModel):
    ui_language: UILanguage | None = None
    density: UIDensity | None = None
    contrast: UIContrast | None = None
    font_scale: UIFontScale | None = None
    reduce_motion: bool | None = None
    show_keyboard_hints: bool | None = None
    document_page_window: int | None = Field(default=None, ge=2, le=30)
    document_text_zoom: int | None = Field(default=None, ge=75, le=175)
    remember_last_workspace: bool | None = None


class OnboardingProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    completed_steps_json: list[str]
    current_step: str | None
    completed_at: datetime | None
    dismissed_at: datetime | None
    updated_at: datetime


class OnboardingProgressUpdate(BaseModel):
    completed_steps: list[str] | None = None
    current_step: str | None = Field(default=None, max_length=80)
    complete: bool = False
    dismiss: bool = False
