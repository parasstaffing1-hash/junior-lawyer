from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experience import UserExperiencePreference, UserOnboardingProgress
from app.services.security.context import ActorContext


ONBOARDING_STEPS = {
    "profile",
    "first_matter",
    "first_document",
    "search",
    "keyboard",
}


def normalize_steps(steps: list[str] | None) -> list[str]:
    if not steps:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in steps:
        key = str(raw).strip().casefold()
        if key in ONBOARDING_STEPS and key not in seen:
            seen.add(key)
            out.append(key)
    return out


async def get_preferences(db: AsyncSession, actor: ActorContext) -> UserExperiencePreference:
    row = await db.scalar(select(UserExperiencePreference).where(UserExperiencePreference.membership_id == actor.membership_id))
    if row is None:
        row = UserExperiencePreference(organization_id=actor.organization_id, membership_id=actor.membership_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def update_preferences(db: AsyncSession, actor: ActorContext, updates: dict) -> UserExperiencePreference:
    row = await get_preferences(db, actor)
    allowed = {
        "ui_language", "density", "contrast", "font_scale", "reduce_motion", "show_keyboard_hints",
        "document_page_window", "document_text_zoom", "remember_last_workspace",
    }
    for key, value in updates.items():
        if key in allowed and value is not None:
            setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


async def get_onboarding(db: AsyncSession, actor: ActorContext) -> UserOnboardingProgress:
    row = await db.scalar(select(UserOnboardingProgress).where(UserOnboardingProgress.membership_id == actor.membership_id))
    if row is None:
        row = UserOnboardingProgress(organization_id=actor.organization_id, membership_id=actor.membership_id, completed_steps_json=[])
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def update_onboarding(db: AsyncSession, actor: ActorContext, payload) -> UserOnboardingProgress:
    row = await get_onboarding(db, actor)
    if payload.completed_steps is not None:
        row.completed_steps_json = normalize_steps(payload.completed_steps)
    if payload.current_step is not None:
        row.current_step = payload.current_step.strip() or None
    now = datetime.now(timezone.utc)
    if payload.complete:
        row.completed_steps_json = sorted(ONBOARDING_STEPS)
        row.completed_at = now
        row.dismissed_at = None
    if payload.dismiss:
        row.dismissed_at = now
    await db.commit()
    await db.refresh(row)
    return row
