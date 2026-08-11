from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.experience import ExperiencePreferenceRead, ExperiencePreferenceUpdate, OnboardingProgressRead, OnboardingProgressUpdate
from app.services.experience import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/experience", tags=["experience"])


@router.get("/preferences", response_model=ExperiencePreferenceRead)
async def preferences(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ExperiencePreferenceRead.model_validate(await service.get_preferences(db, actor))


@router.patch("/preferences", response_model=ExperiencePreferenceRead)
async def patch_preferences(payload: ExperiencePreferenceUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ExperiencePreferenceRead.model_validate(await service.update_preferences(db, actor, payload.model_dump(exclude_unset=True)))


@router.get("/onboarding", response_model=OnboardingProgressRead)
async def onboarding(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return OnboardingProgressRead.model_validate(await service.get_onboarding(db, actor))


@router.patch("/onboarding", response_model=OnboardingProgressRead)
async def patch_onboarding(payload: OnboardingProgressUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return OnboardingProgressRead.model_validate(await service.update_onboarding(db, actor, payload))
