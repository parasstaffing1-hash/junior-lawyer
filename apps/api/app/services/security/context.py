from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from app.models.security import OrganizationRole


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: UUID
    membership_id: UUID
    organization_id: UUID
    email: str
    display_name: str
    role: OrganizationRole
    mfa_enrolled: bool
    session_id: UUID | None = None


_current_actor: ContextVar[ActorContext | None] = ContextVar("jl_current_actor", default=None)


def get_current_actor() -> ActorContext | None:
    return _current_actor.get()


def set_current_actor(actor: ActorContext | None):
    return _current_actor.set(actor)


def reset_current_actor(token) -> None:
    _current_actor.reset(token)
