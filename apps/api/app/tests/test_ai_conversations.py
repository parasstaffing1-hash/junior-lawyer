from uuid import uuid4

import pytest

pytest.importorskip("aiosqlite")
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403 - register every ORM model for metadata
from app.models.ai import ConversationMessageRole, ConversationStatus
from app.models.security import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
    SecurityUser,
)
from app.services.ai.conversations import (
    build_context,
    create_conversation,
    delete_conversation,
    derive_title,
    get_conversation,
    list_conversations,
    post_message,
    rename_conversation,
    set_status,
)
from app.services.ai.providers import ProviderRegistry, StaticProvider
from app.services.security.context import ActorContext
from app.services.security.crypto import hash_password


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def make_actor(db: AsyncSession, *, slug: str = "example-chambers") -> ActorContext:
    organization = Organization(name=f"Firm {slug}", slug=slug)
    db.add(organization)
    await db.flush()
    user = SecurityUser(
        email=f"lawyer@{slug}.example",
        display_name="Example Lawyer",
        password_hash=hash_password("correct-horse-battery-staple"),
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


def registry() -> ProviderRegistry:
    return ProviderRegistry({"local": StaticProvider("Section 138 requires written notice [S1].")})


@pytest.fixture(autouse=True)
def local_model_enabled(monkeypatch):
    """Route to the local tier so the injected StaticProvider is reached.

    Without this the router blocks every run (`ai_enabled` is false by
    default), and the thread would only ever record empty answers.
    """
    from app.core.config import settings as live

    monkeypatch.setattr(live, "ai_enabled", True)
    monkeypatch.setattr(live, "ai_local_enabled", True)
    monkeypatch.setattr(live, "ai_local_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(live, "ai_local_model", "local-legal-model")


# --- titles ------------------------------------------------------------------


def test_title_is_derived_from_the_first_sentence():
    assert derive_title("What is the limitation period? I need it for an appeal.") == (
        "What is the limitation period?"
    )
    assert derive_title("   ") == "New conversation"
    assert derive_title("x" * 400).endswith("…")
    assert len(derive_title("x" * 400)) <= 120


# --- context -----------------------------------------------------------------


def test_context_labels_each_speaker_and_keeps_the_question_last():
    class Msg:
        def __init__(self, role, content):
            self.role, self.content = role, content

    history = [
        Msg(ConversationMessageRole.USER, "What notice is required?"),
        Msg(ConversationMessageRole.ASSISTANT, "Written notice within 30 days."),
    ]
    rendered = build_context(history, "And if it is served late?")
    assert "Lawyer: What notice is required?" in rendered
    assert "Assistant: Written notice within 30 days." in rendered
    assert rendered.strip().endswith("Current question: And if it is served late?")


def test_context_is_just_the_question_when_the_thread_is_empty():
    assert build_context([], "What is the limitation period?") == "What is the limitation period?"


# --- threads -----------------------------------------------------------------


async def test_a_thread_records_both_turns_and_links_the_run(db):
    actor = await make_actor(db)
    conversation = await create_conversation(db, actor)
    question, answer, run = await post_message(
        db,
        actor,
        conversation.id,
        question="What notice does section 138 require?",
        providers=registry(),
        allow_local_for_high_complexity=True,
    )

    assert question.role == ConversationMessageRole.USER
    assert answer.role == ConversationMessageRole.ASSISTANT
    assert question.ordinal == 0 and answer.ordinal == 1
    # The answer points at the run, which is where citations already live.
    assert answer.run_id == run.id
    assert answer.content == run.response_text

    detail = await get_conversation(db, actor, conversation.id)
    assert detail.message_count == 2
    assert detail.last_message_at is not None
    # An untitled thread takes its name from the opening question.
    assert detail.title == "What notice does section 138 require?"


async def test_a_follow_up_carries_the_earlier_turns_into_the_run(db):
    actor = await make_actor(db)
    conversation = await create_conversation(db, actor)
    await post_message(
        db, actor, conversation.id, question="What notice is required?", providers=registry(), allow_local_for_high_complexity=True
    )
    _, _, run = await post_message(
        db, actor, conversation.id, question="And if it is served late?", providers=registry(), allow_local_for_high_complexity=True
    )

    assert "Earlier in this conversation:" in run.query
    assert "What notice is required?" in run.query
    assert run.query.strip().endswith("Current question: And if it is served late?")

    detail = await get_conversation(db, actor, conversation.id)
    assert [m.ordinal for m in detail.messages] == [0, 1, 2, 3]


async def test_an_explicit_title_is_not_overwritten(db):
    actor = await make_actor(db)
    conversation = await create_conversation(db, actor, title="Cheque bounce")
    await post_message(
        db, actor, conversation.id, question="What notice is required?", providers=registry(), allow_local_for_high_complexity=True
    )
    assert (await get_conversation(db, actor, conversation.id)).title == "Cheque bounce"


async def test_archived_threads_refuse_new_messages(db):
    actor = await make_actor(db)
    conversation = await create_conversation(db, actor)
    await set_status(db, actor, conversation.id, ConversationStatus.ARCHIVED)
    with pytest.raises(HTTPException) as exc:
        await post_message(db, actor, conversation.id, question="Anything?", providers=registry(), allow_local_for_high_complexity=True)
    assert exc.value.status_code == 409


# --- tenancy -----------------------------------------------------------------


async def test_a_thread_is_invisible_to_another_organization(db):
    owner = await make_actor(db, slug="owner-firm")
    stranger = await make_actor(db, slug="other-firm")
    conversation = await create_conversation(db, owner, title="Privileged strategy")

    assert await list_conversations(db, stranger) == []
    for call in (
        get_conversation(db, stranger, conversation.id),
        rename_conversation(db, stranger, conversation.id, "renamed"),
        delete_conversation(db, stranger, conversation.id),
        post_message(db, stranger, conversation.id, question="Hello?", providers=registry(), allow_local_for_high_complexity=True),
    ):
        with pytest.raises(HTTPException) as exc:
            await call
        # 404 rather than 403: never confirm another firm's thread exists.
        assert exc.value.status_code == 404


async def test_a_missing_thread_is_a_404(db):
    actor = await make_actor(db)
    with pytest.raises(HTTPException) as exc:
        await get_conversation(db, actor, uuid4())
    assert exc.value.status_code == 404


async def test_listing_is_scoped_filtered_and_most_recent_first(db):
    actor = await make_actor(db)
    first = await create_conversation(db, actor, title="First")
    second = await create_conversation(db, actor, title="Second")
    await post_message(
        db, actor, first.id, question="What notice is required?", providers=registry(), allow_local_for_high_complexity=True
    )

    listed = await list_conversations(db, actor)
    assert [c.title for c in listed][0] == "First"  # it has the newest message
    assert {c.title for c in listed} == {"First", "Second"}

    await set_status(db, actor, second.id, ConversationStatus.ARCHIVED)
    active = await list_conversations(db, actor, status=ConversationStatus.ACTIVE)
    assert [c.title for c in active] == ["First"]


async def test_deleting_a_thread_removes_its_messages(db):
    actor = await make_actor(db)
    conversation = await create_conversation(db, actor)
    await post_message(
        db, actor, conversation.id, question="What notice is required?", providers=registry(), allow_local_for_high_complexity=True
    )
    await delete_conversation(db, actor, conversation.id)
    with pytest.raises(HTTPException):
        await get_conversation(db, actor, conversation.id)
