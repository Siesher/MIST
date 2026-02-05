"""Student profile and analytics endpoints."""

from fastapi import APIRouter, Query
from datetime import datetime

from backend.app.schemas.chat import (
    StudentProfileResponse,
    AnalyticsResponse,
    KnowledgeStateResponse,
    ProgressByDay,
)
from backend.app.services.orchestrator_service import get_orchestrator_service

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me/profile", response_model=StudentProfileResponse)
async def get_profile():
    """Get current student profile."""
    service = await get_orchestrator_service()
    data = service.get_student_profile()
    return StudentProfileResponse(**data)


@router.get("/me/analytics", response_model=AnalyticsResponse)
async def get_analytics(period: str = Query("week", regex="^(day|week|month|all)$")):
    """Get analytics data for a time period."""
    service = await get_orchestrator_service()
    data = service.get_analytics(period=period)

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
async def get_knowledge_state():
    """Get current knowledge state."""
    service = await get_orchestrator_service()
    data = service.get_knowledge_state()
    return KnowledgeStateResponse(**data)
