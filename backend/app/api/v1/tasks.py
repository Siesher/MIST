"""Task endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.auth import get_optional_user, require_llm_budget
from backend.app.models.database import get_db
from backend.app.models.tables import UserTable
from backend.app.schemas.chat import (
    Difficulty,
    GenerateTaskRequest,
    RecommendedTasksResponse,
    TaskResponse,
    TopicInfo,
    TopicsListResponse,
)
from backend.app.services.orchestrator_service import get_orchestrator_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/topics", response_model=TopicsListResponse)
async def list_topics():
    """List available math topics."""
    service = await get_orchestrator_service()
    topics_data = service.get_available_topics()

    topics = []
    for t in topics_data:
        topics.append(
            TopicInfo(
                id=t["id"],
                name=t["name"],
                name_ru=t["name_ru"],
                difficulties=[Difficulty(d) for d in t["difficulties"]],
            )
        )

    return TopicsListResponse(topics=topics)


@router.post("/generate", response_model=TaskResponse)
async def generate_task(
    request: GenerateTaskRequest,
    _user: UserTable | None = Depends(require_llm_budget),
):
    """Generate a new math task."""
    service = await get_orchestrator_service()
    task = await service.generate_task(
        topic=request.topic,
        difficulty=request.difficulty.value,
        avoid_recent=request.avoid_recent,
    )

    if not task:
        raise HTTPException(status_code=500, detail="Failed to generate task")

    return TaskResponse(
        id=task["id"],
        topic=task["topic"],
        difficulty=Difficulty(task["difficulty"]),
        problem=task["problem"],
        hints=task.get("hints", []),
        skills=task.get("skills", []),
    )


@router.get("/recommended", response_model=RecommendedTasksResponse)
async def get_recommended_tasks(
    count: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
):
    """Get personalized task recommendations (by mastery; anonymous → foundational)."""
    service = await get_orchestrator_service()
    result = await service.get_recommended_tasks(db=db, user_id=user.id if user else None, count=count)

    tasks = []
    for t in result.get("tasks", []):
        tasks.append(
            TaskResponse(
                id=t["id"],
                topic=t["topic"],
                difficulty=Difficulty(t["difficulty"]),
                problem=t["problem"],
                hints=t.get("hints", []),
                skills=t.get("skills", []),
            )
        )

    return RecommendedTasksResponse(
        tasks=tasks,
        reasoning=result.get("reasoning", ""),
    )
