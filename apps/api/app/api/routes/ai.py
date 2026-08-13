from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.ai import ConversationStatus
from app.schemas.ai import (
    AIPrepareResponse,
    AIProviderStatusRead,
    AIReasoningRequest,
    AIReviewRequest,
    AIRunRead,
    ConversationCreate,
    ConversationDetail,
    ConversationMessageCreate,
    ConversationMessageRead,
    ConversationRead,
    ConversationRename,
    ConversationStatusUpdate,
    ConversationTurn,
)
from app.services.ai import conversations, service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/ai", tags=["verified-ai"])


@router.get("/providers", response_model=AIProviderStatusRead)
async def providers() -> AIProviderStatusRead:
    return AIProviderStatusRead.model_validate(await service.provider_status())


@router.post("/prepare", response_model=AIPrepareResponse)
async def prepare(
    payload: AIReasoningRequest,
    db: AsyncSession = Depends(get_db),
) -> AIPrepareResponse:
    return AIPrepareResponse.model_validate(await service.prepare_reasoning(db, payload))


@router.post("/runs", response_model=AIRunRead, status_code=status.HTTP_201_CREATED)
async def run(
    payload: AIReasoningRequest,
    db: AsyncSession = Depends(get_db),
) -> AIRunRead:
    return AIRunRead.model_validate(await service.run_reasoning(db, payload))


@router.get("/runs", response_model=list[AIRunRead])
async def runs(
    matter_id: UUID | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[AIRunRead]:
    return [AIRunRead.model_validate(row) for row in await service.list_runs(db, matter_id=matter_id, limit=limit)]


@router.get("/runs/{run_id}", response_model=AIRunRead)
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)) -> AIRunRead:
    return AIRunRead.model_validate(await service.get_run(db, run_id))


@router.patch("/runs/{run_id}/review", response_model=AIRunRead)
async def review_run(
    run_id: UUID,
    payload: AIReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> AIRunRead:
    return AIRunRead.model_validate(await service.review_run(db, run_id, payload))


# --- conversations -----------------------------------------------------------


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    row = await conversations.create_conversation(
        db,
        actor,
        title=payload.title,
        matter_id=payload.matter_id,
        jurisdiction=payload.jurisdiction,
        output_language=payload.output_language,
        document_ids=payload.document_ids,
    )
    return ConversationRead.model_validate(row)


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    matter_id: UUID | None = None,
    conversation_status: ConversationStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationRead]:
    rows = await conversations.list_conversations(
        db, actor, matter_id=matter_id, status=conversation_status, limit=limit
    )
    return [ConversationRead.model_validate(row) for row in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    row = await conversations.get_conversation(db, actor, conversation_id)
    return ConversationDetail(
        conversation=ConversationRead.model_validate(row),
        messages=[ConversationMessageRead.model_validate(m) for m in row.messages],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
async def rename_conversation(
    conversation_id: UUID,
    payload: ConversationRename,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    row = await conversations.rename_conversation(db, actor, conversation_id, payload.title)
    return ConversationRead.model_validate(row)


@router.patch("/conversations/{conversation_id}/status", response_model=ConversationRead)
async def set_conversation_status(
    conversation_id: UUID,
    payload: ConversationStatusUpdate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    row = await conversations.set_status(db, actor, conversation_id, payload.status)
    return ConversationRead.model_validate(row)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> None:
    await conversations.delete_conversation(db, actor, conversation_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationTurn,
    status_code=status.HTTP_201_CREATED,
)
async def post_conversation_message(
    conversation_id: UUID,
    payload: ConversationMessageCreate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> ConversationTurn:
    question, answer, run = await conversations.post_message(
        db,
        actor,
        conversation_id,
        question=payload.question,
        task_type=payload.task_type,
        prefer_local=payload.prefer_local,
        allow_remote=payload.allow_remote,
        allow_local_for_high_complexity=payload.allow_local_for_high_complexity,
        include_corpus=payload.include_corpus,
        max_sources=payload.max_sources,
        max_input_tokens=payload.max_input_tokens,
        max_output_tokens=payload.max_output_tokens,
    )
    conversation = await conversations.get_conversation(db, actor, conversation_id)
    return ConversationTurn(
        conversation=ConversationRead.model_validate(conversation),
        question=ConversationMessageRead.model_validate(question),
        answer=ConversationMessageRead.model_validate(answer),
        run=AIRunRead.model_validate(run),
    )
