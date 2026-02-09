"""Chat endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.database import get_db
from backend.app.schemas.chat import (
    SendMessageRequest,
    ChatResponseSchema,
    HintResponseSchema,
    SolutionResponseSchema,
    TutorResponseData,
    SessionState,
    TutorMoveType,
)
from backend.app.services.orchestrator_service import get_orchestrator_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{session_id}/message", response_model=ChatResponseSchema)
async def send_message(session_id: str, request: SendMessageRequest, db: AsyncSession = Depends(get_db)):
    """Send a chat message and get tutor response (non-streaming)."""
    service = await get_orchestrator_service()
    session = await service.get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await service.process_message(db, session_id, request.content)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to process message")

    tr = result["tutor_response"]
    move = None
    if tr.get("move_type"):
        try:
            move = TutorMoveType(tr["move_type"])
        except ValueError:
            move = TutorMoveType.scaffolding

    return ChatResponseSchema(
        message_id=result["message_id"],
        tutor_response=TutorResponseData(
            content=tr["content"],
            move_type=move,
            is_correct=tr.get("is_correct"),
            thinking=tr.get("thinking"),
        ),
        session_state=SessionState(
            is_solved=result["session_state"]["is_solved"],
            hints_used=result["session_state"]["hints_used"],
            attempts=result["session_state"]["attempts"],
        ),
        knowledge_update=result.get("knowledge_update"),
    )


@router.get("/{session_id}/hint", response_model=HintResponseSchema)
async def get_hint(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get the next progressive hint."""
    service = await get_orchestrator_service()
    session = await service.get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await service.get_hint(db, session_id)
    if not result:
        raise HTTPException(status_code=400, detail="No hints available")

    return HintResponseSchema(**result)


@router.post("/{session_id}/solution", response_model=SolutionResponseSchema)
async def reveal_solution(session_id: str, db: AsyncSession = Depends(get_db)):
    """Reveal the solution (penalized)."""
    service = await get_orchestrator_service()
    session = await service.get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await service.reveal_solution(db, session_id)
    if not result:
        raise HTTPException(status_code=400, detail="No task associated with this session")

    return SolutionResponseSchema(**result)
