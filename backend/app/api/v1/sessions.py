"""Session management endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.app.schemas.chat import (
    CreateSessionRequest,
    ChangeModeRequest,
    ChangeModeResponse,
    SessionResponse,
    SessionWithTaskResponse,
    SessionDetailResponse,
    SessionListResponse,
    TaskResponse,
    MessageResponse,
    ChatMode,
    Difficulty,
    SessionStatus,
    MessageRole,
    TutorMoveType,
)
from backend.app.services.orchestrator_service import get_orchestrator_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionWithTaskResponse, status_code=201)
async def create_session(request: CreateSessionRequest):
    """Create a new tutoring session."""
    service = await get_orchestrator_service()
    session = await service.create_session(
        topic=request.topic,
        difficulty=request.difficulty.value if request.difficulty else None,
        custom_problem=request.custom_problem,
        mode=request.mode.value if request.mode else None,
    )

    task_resp = None
    if session.task:
        task_resp = TaskResponse(
            id=session.task["id"],
            topic=session.task["topic"],
            difficulty=Difficulty(session.task["difficulty"]),
            problem=session.task["problem"],
            hints=session.task.get("hints", []),
            skills=session.task.get("skills", []),
        )

    welcome = session.messages[0].content if session.messages else None

    return SessionWithTaskResponse(
        id=session.id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        topic=session.topic,
        difficulty=Difficulty(session.difficulty) if session.difficulty else None,
        status=SessionStatus(session.status),
        mode=ChatMode(session.mode),
        message_count=len(session.messages),
        is_solved=session.is_solved,
        hints_used=session.hints_used,
        task=task_resp,
        welcome_message=welcome,
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
):
    """List all sessions."""
    service = await get_orchestrator_service()
    result = await service.list_sessions(page=page, limit=limit, status=status)

    sessions = []
    for s in result["sessions"]:
        sessions.append(SessionResponse(
            id=s.id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            topic=s.topic,
            difficulty=Difficulty(s.difficulty) if s.difficulty else None,
            status=SessionStatus(s.status),
            mode=ChatMode(s.mode),
            message_count=len(s.messages),
            is_solved=s.is_solved,
            hints_used=s.hints_used,
        ))

    return SessionListResponse(
        sessions=sessions,
        total=result["total"],
        page=result["page"],
        pages=result["pages"],
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """Get session details with messages."""
    service = await get_orchestrator_service()
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = []
    for m in session.messages:
        messages.append(MessageResponse(
            id=m.id,
            session_id=session.id,
            role=MessageRole(m.role),
            content=m.content,
            timestamp=m.timestamp,
            move_type=TutorMoveType(m.move_type) if m.move_type else None,
            is_correct=m.is_correct,
        ))

    task_resp = None
    if session.task:
        task_resp = TaskResponse(
            id=session.task["id"],
            topic=session.task["topic"],
            difficulty=Difficulty(session.task["difficulty"]),
            problem=session.task["problem"],
            hints=session.task.get("hints", []),
            skills=session.task.get("skills", []),
        )

    return SessionDetailResponse(
        id=session.id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        topic=session.topic,
        difficulty=Difficulty(session.difficulty) if session.difficulty else None,
        status=SessionStatus(session.status),
        mode=ChatMode(session.mode),
        message_count=len(session.messages),
        is_solved=session.is_solved,
        hints_used=session.hints_used,
        messages=messages,
        task=task_resp,
    )


@router.patch("/{session_id}/mode", response_model=ChangeModeResponse)
async def change_session_mode(session_id: str, request: ChangeModeRequest):
    """Change the mode of an existing session."""
    service = await get_orchestrator_service()
    result = await service.change_mode(session_id, request.mode.value)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChangeModeResponse(
        session_id=result["session_id"],
        previous_mode=ChatMode(result["previous_mode"]),
        current_mode=ChatMode(result["current_mode"]),
        message=result["message"],
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """Delete a session."""
    service = await get_orchestrator_service()
    deleted = await service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
