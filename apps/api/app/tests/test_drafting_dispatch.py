"""Sending a draft: the guards that stand between a draft and an adversary."""

from uuid import uuid4

import pytest

pytest.importorskip("aiosqlite")
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403 - register every ORM model for metadata
from app.models.drafting import (
    LegalDraft,
    LegalDraftLanguage,
    LegalDraftSection,
    LegalDraftStatus,
    LegalDraftType,
)
from app.models.matter import Matter
from app.models.security import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
    SecurityUser,
)
from app.services.drafting import dispatch
from app.services.security.context import ActorContext
from app.services.security.crypto import hash_password


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def make_actor(db: AsyncSession) -> ActorContext:
    organization = Organization(name="Example Chambers", slug="example-chambers")
    db.add(organization)
    await db.flush()
    user = SecurityUser(
        email="lawyer@example.com", display_name="Example Lawyer", password_hash=hash_password("x" * 14)
    )
    db.add(user)
    await db.flush()
    membership = OrganizationMembership(
        organization_id=organization.id, user_id=user.id, role=OrganizationRole.LAWYER
    )
    db.add(membership)
    await db.commit()
    return ActorContext(
        user_id=user.id,
        membership_id=membership.id,
        organization_id=organization.id,
        email=user.email,
        display_name=user.display_name,
        role=OrganizationRole.LAWYER,
        mfa_enrolled=False,
    )


async def make_draft(db: AsyncSession, status: LegalDraftStatus) -> LegalDraft:
    matter = Matter(title="Cheque dishonour — demo")
    db.add(matter)
    await db.flush()
    draft = LegalDraft(
        matter_id=matter.id,
        title="Legal Notice — cheque dishonour",
        draft_type=LegalDraftType.LEGAL_NOTICE,
        language=LegalDraftLanguage.ENGLISH,
        status=status,
    )
    db.add(draft)
    await db.flush()
    db.add_all(
        [
            LegalDraftSection(
                draft_id=draft.id, position=1, section_key="address",
                title_en="Address & Subject", body_en="To the addressee.",
            ),
            LegalDraftSection(
                draft_id=draft.id, position=0, section_key="heading",
                title_en="Heading", body_en="Under instructions from my client.",
            ),
        ]
    )
    await db.commit()
    await db.refresh(draft)
    return draft


# --- rendering ---------------------------------------------------------------


async def test_the_body_follows_section_order_not_insertion_order(db):
    draft = await make_draft(db, LegalDraftStatus.APPROVED)
    body = dispatch.render_plain_text(draft)
    assert body.index("Under instructions") < body.index("To the addressee")
    assert "HEADING" in body  # headings are upper-cased in the plain-text body


# --- the guards --------------------------------------------------------------


async def test_an_unapproved_draft_cannot_be_sent(db):
    actor = await make_actor(db)
    for status in (LegalDraftStatus.DRAFT, LegalDraftStatus.IN_REVIEW, LegalDraftStatus.SUPERSEDED):
        draft = await make_draft(db, status)
        with pytest.raises(HTTPException) as exc:
            await dispatch.send_draft(
                db, actor, draft.id,
                to=["opposite@example.com"], recipient_kind="opposite_party", confirm=True,
            )
        assert exc.value.status_code == 409
        assert "approved" in exc.value.detail


async def test_sending_requires_explicit_confirmation(db):
    actor = await make_actor(db)
    draft = await make_draft(db, LegalDraftStatus.APPROVED)
    with pytest.raises(HTTPException) as exc:
        await dispatch.send_draft(
            db, actor, draft.id,
            to=["client@example.com"], recipient_kind="client", confirm=False,
        )
    # 428 Precondition Required: the request is well formed but unconfirmed.
    assert exc.value.status_code == 428


async def test_confirmation_alone_does_not_override_the_approval_gate(db):
    # The two guards are independent; confirming must not smuggle a draft out.
    actor = await make_actor(db)
    draft = await make_draft(db, LegalDraftStatus.DRAFT)
    with pytest.raises(HTTPException) as exc:
        await dispatch.send_draft(
            db, actor, draft.id, to=["a@example.com"], recipient_kind="client", confirm=True
        )
    assert exc.value.status_code == 409


async def test_an_unknown_recipient_kind_is_refused(db):
    actor = await make_actor(db)
    draft = await make_draft(db, LegalDraftStatus.APPROVED)
    with pytest.raises(HTTPException) as exc:
        await dispatch.send_draft(
            db, actor, draft.id, to=["a@example.com"], recipient_kind="everyone", confirm=True
        )
    assert exc.value.status_code == 422


async def test_an_empty_recipient_list_is_refused(db):
    actor = await make_actor(db)
    draft = await make_draft(db, LegalDraftStatus.APPROVED)
    with pytest.raises(HTTPException) as exc:
        await dispatch.send_draft(db, actor, draft.id, to=[], recipient_kind="client", confirm=True)
    assert exc.value.status_code == 422


async def test_a_missing_draft_is_a_404(db):
    actor = await make_actor(db)
    with pytest.raises(HTTPException) as exc:
        await dispatch.send_draft(
            db, actor, uuid4(), to=["a@example.com"], recipient_kind="client", confirm=True
        )
    assert exc.value.status_code == 404


async def test_without_an_email_connection_the_failure_names_the_fix(db):
    # Every guard passed; there is simply nothing configured to send through.
    actor = await make_actor(db)
    draft = await make_draft(db, LegalDraftStatus.APPROVED)
    with pytest.raises(HTTPException) as exc:
        await dispatch.send_draft(
            db, actor, draft.id, to=["a@example.com"], recipient_kind="client", confirm=True
        )
    assert exc.value.status_code == 422
    assert "Integrations" in exc.value.detail
