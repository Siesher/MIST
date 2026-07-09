"""Student profile and analytics endpoints."""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.api.v1.auth import get_optional_user
from backend.app.models.database import get_db
from backend.app.models.tables import SessionTable, UserTable
from backend.app.schemas.chat import (
    AnalyticsResponse,
    KnowledgeStateResponse,
    ProgressByDay,
    StudentProfileResponse,
)
from backend.app.services.mastery_service import compute_mastery, mastery_by_skill
from backend.app.services.orchestrator_service import get_orchestrator_service

router = APIRouter(prefix="/students", tags=["students"])


async def _recent_rows(db: AsyncSession, user: UserTable | None, limit: int = 50):
    """Load the caller's most recent sessions with messages (mirrors ``/dream``).

    Args:
        db: Async database session.
        user: Authenticated user, or ``None`` for anonymous callers.
        limit: Maximum number of recent sessions to load.

    Returns:
        A sequence of :class:`SessionTable` rows ordered by ``updated_at`` desc,
        each with its ``messages`` eagerly loaded.
    """
    q = (
        select(SessionTable)
        .options(selectinload(SessionTable.messages))
        .where(SessionTable.user_id == (user.id if user else None))
        .order_by(SessionTable.updated_at.desc())
        .limit(limit)
    )
    return (await db.execute(q)).scalars().all()


@router.get("/me/profile", response_model=StudentProfileResponse)
async def get_profile(db: AsyncSession = Depends(get_db)):
    """Get current student profile."""
    service = await get_orchestrator_service()
    data = await service.get_student_profile(db)
    return StudentProfileResponse(**data)


@router.get("/me/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    period: str = Query("week", pattern="^(day|week|month|all)$"), db: AsyncSession = Depends(get_db)
):
    """Get analytics data for a time period."""
    service = await get_orchestrator_service()
    data = await service.get_analytics(db, period=period)

    progress = [ProgressByDay(**p) for p in data.get("progress_by_day", [])]

    return AnalyticsResponse(
        period_start=datetime.fromisoformat(data["period_start"]),
        period_end=datetime.fromisoformat(data["period_end"]),
        sessions_count=data["sessions_count"],
        tasks_attempted=data["tasks_attempted"],
        tasks_solved=data["tasks_solved"],
        avg_session_minutes=data["avg_session_minutes"],
        avg_hints_per_task=data["avg_hints_per_task"],
        progress_by_day=progress,
    )


@router.get("/me/knowledge", response_model=KnowledgeStateResponse)
async def get_knowledge_state(
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
):
    """Get current knowledge state (real BKT mastery; weakest topics as next focus).

    Args:
        db: Async database session (injected).
        user: Authenticated user, or ``None`` for anonymous callers (injected).

    Returns:
        A :class:`KnowledgeStateResponse` with per-skill mastery and the three
        weakest topics as the recommended next focus.
    """
    rows = await _recent_rows(db, user)
    signals = compute_mastery(rows)
    return KnowledgeStateResponse(
        mastery_by_skill=mastery_by_skill(signals),
        skill_dependencies={},
        recommended_next=[s.topic for s in signals[:3]],  # weakest first
    )


@router.get("/me/mastery")
async def get_mastery(
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
) -> dict:
    """Real per-topic BKT mastery for the current (or anonymous) student.

    Args:
        db: Async database session (injected).
        user: Authenticated user, or ``None`` for anonymous callers (injected).

    Returns:
        A dict with ``topics`` (per-topic mastery signals, weakest first) and a
        flattened ``mastery_by_skill`` ``{topic: p_known}`` map.
    """
    rows = await _recent_rows(db, user)
    signals = compute_mastery(rows)
    return {
        "topics": [asdict(s) for s in signals],
        "mastery_by_skill": mastery_by_skill(signals),
    }
