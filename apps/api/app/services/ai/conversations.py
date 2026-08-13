"""Conversation threads over the existing reasoning engine.

A thread is bookkeeping, not a second engine: every assistant turn is still an
AIRun, so sources, claims, citations, verification, routing and usage
accounting are exactly the ones the single-shot path already produces. What the
thread adds is continuity — prior turns are folded into the next question, and
pinned documents survive across turns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import (
    AIConversation,
    AIConversationMessage,
    AIRun,
    AITaskType,
    ConversationMessageRole,
    ConversationStatus,
)
from app.schemas.ai import AIReasoningRequest
from app.services.ai.providers import ProviderRegistry
from app.services.ai.service import run_reasoning
from app.services.security.context import ActorContext

# How many prior turns to replay into a follow-up. Enough for a lawyer to say
# "and what about clause 7?", short enough that the input budget stays for
# retrieved sources rather than history.
CONTEXT_TURNS = 6
MAX_TITLE_LENGTH = 120


def _now() -> datetime:
    return datetime.now(timezone.utc)


def derive_title(question: str) -> str:
    """First sentence of the opening question, trimmed to fit."""
    cleaned = " ".join((question or "").split())
    if not cleaned:
        return "New conversation"
    for terminator in (". ", "? ", "! "):
        head, _, _ = cleaned.partition(terminator)
        if head != cleaned and len(head) >= 12:
            cleaned = head + terminator.strip()
            break
    if len(cleaned) <= MAX_TITLE_LENGTH:
        return cleaned
    return cleaned[: MAX_TITLE_LENGTH - 1].rstrip() + "…"


async def _get_owned(db: AsyncSession, actor: ActorContext, conversation_id: UUID) -> AIConversation:
    row = await db.get(AIConversation, conversation_id)
    if not row or row.organization_id != actor.organization_id:
        # Same answer either way: never confirm another firm's thread exists.
        raise HTTPException(status_code=404, detail="Conversation not found")
    return row


async def create_conversation(
    db: AsyncSession,
    actor: ActorContext,
    *,
    title: str | None = None,
    matter_id: UUID | None = None,
    jurisdiction: str = "India",
    output_language: str = "en",
    document_ids: list[UUID] | None = None,
) -> AIConversation:
    row = AIConversation(
        organization_id=actor.organization_id,
        created_by_user_id=actor.user_id,
        matter_id=matter_id,
        title=(title or "New conversation")[:250],
        jurisdiction=jurisdiction,
        output_language=output_language,
        document_ids_json=[str(value) for value in (document_ids or [])],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_conversations(
    db: AsyncSession,
    actor: ActorContext,
    *,
    matter_id: UUID | None = None,
    status: ConversationStatus | None = None,
    limit: int = 50,
) -> list[AIConversation]:
    stmt = (
        select(AIConversation)
        .where(AIConversation.organization_id == actor.organization_id)
        .order_by(
            func.coalesce(AIConversation.last_message_at, AIConversation.created_at).desc()
        )
        .limit(limit)
    )
    if matter_id:
        stmt = stmt.where(AIConversation.matter_id == matter_id)
    if status:
        stmt = stmt.where(AIConversation.status == status)
    return list((await db.scalars(stmt)).unique().all())


async def get_conversation(
    db: AsyncSession, actor: ActorContext, conversation_id: UUID
) -> AIConversation:
    row = await _get_owned(db, actor, conversation_id)
    # The identity map can hold a `messages` collection loaded before the last
    # turn was written, so read it back rather than trusting what is cached.
    await db.refresh(row, attribute_names=["messages"])
    return row


async def rename_conversation(
    db: AsyncSession, actor: ActorContext, conversation_id: UUID, title: str
) -> AIConversation:
    row = await _get_owned(db, actor, conversation_id)
    row.title = title[:250]
    await db.commit()
    await db.refresh(row)
    return row


async def set_status(
    db: AsyncSession, actor: ActorContext, conversation_id: UUID, status: ConversationStatus
) -> AIConversation:
    row = await _get_owned(db, actor, conversation_id)
    row.status = status
    await db.commit()
    await db.refresh(row)
    return row


async def delete_conversation(
    db: AsyncSession, actor: ActorContext, conversation_id: UUID
) -> None:
    row = await _get_owned(db, actor, conversation_id)
    await db.delete(row)
    await db.commit()


def build_context(messages: list[AIConversationMessage], question: str) -> str:
    """Fold recent turns into the question the engine actually receives.

    Prior answers are labelled as such so the model treats them as its own
    earlier statements rather than as retrieved authority — a distinction that
    matters when the verification pass checks every claim against sources.
    """
    history = [m for m in messages if m.content][-CONTEXT_TURNS:]
    if not history:
        return question
    lines = ["Earlier in this conversation:"]
    for message in history:
        speaker = "Lawyer" if message.role == ConversationMessageRole.USER else "Assistant"
        lines.append(f"{speaker}: {message.content.strip()}")
    lines.append("")
    lines.append(f"Current question: {question.strip()}")
    return "\n".join(lines)


async def post_message(
    db: AsyncSession,
    actor: ActorContext,
    conversation_id: UUID,
    *,
    question: str,
    task_type: AITaskType = AITaskType.RESEARCH_SYNTHESIS,
    prefer_local: bool = True,
    allow_remote: bool = False,
    # High-complexity reasoning needs an explicit permission, exactly as it does
    # on the single-shot path. A thread must not quietly widen what the router
    # is allowed to do.
    allow_local_for_high_complexity: bool = False,
    include_corpus: bool = True,
    max_sources: int = 12,
    max_input_tokens: int = 6000,
    max_output_tokens: int = 1200,
    providers: ProviderRegistry | None = None,
) -> tuple[AIConversationMessage, AIConversationMessage, AIRun]:
    """Add a question, run it with thread context, and store the answer."""
    conversation = await _get_owned(db, actor, conversation_id)
    if conversation.status == ConversationStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="This conversation is archived")

    # Read the turns back from the database rather than the loaded relationship:
    # after an earlier post in the same session the collection is stale, and a
    # stale count collides with the (conversation_id, ordinal) unique key.
    history = list(
        (
            await db.scalars(
                select(AIConversationMessage)
                .where(AIConversationMessage.conversation_id == conversation.id)
                .order_by(AIConversationMessage.ordinal)
            )
        ).all()
    )
    ordinal = len(history)
    user_message = AIConversationMessage(
        conversation_id=conversation.id,
        ordinal=ordinal,
        role=ConversationMessageRole.USER,
        content=question,
        author_user_id=actor.user_id,
    )
    db.add(user_message)
    await db.flush()

    run = await run_reasoning(
        db,
        AIReasoningRequest(
            matter_id=conversation.matter_id,
            task_type=task_type,
            query=build_context(history, question),
            output_language=conversation.output_language,
            prefer_local=prefer_local,
            allow_remote=allow_remote,
            allow_local_for_high_complexity=allow_local_for_high_complexity,
            include_corpus=include_corpus,
            max_sources=max_sources,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
        ),
        providers=providers,
    )

    assistant_message = AIConversationMessage(
        conversation_id=conversation.id,
        ordinal=ordinal + 1,
        role=ConversationMessageRole.ASSISTANT,
        content=run.response_text or "",
        run_id=run.id,
    )
    db.add(assistant_message)

    if conversation.message_count == 0 and conversation.title == "New conversation":
        conversation.title = derive_title(question)
    conversation.message_count = ordinal + 2
    conversation.last_message_at = _now()

    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)
    await db.refresh(run)
    return user_message, assistant_message, run
