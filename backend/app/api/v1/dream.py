# backend/app/api/v1/dream.py
"""Dreaming endpoints: run a sleep pass, read student memory."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.api.v1.auth import get_current_user
from backend.app.models.database import get_db
from backend.app.models.tables import SessionTable, UserTable
from backend.app.services.orchestrator_service import get_orchestrator_service
from src.memory.memory_files import StudentMemoryFiles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dream", tags=["dreaming"])


def _student_id(user: UserTable | None) -> str:
    """Return a filesystem-safe student id for the memory store.

    Args:
        user: Authenticated user, or ``None`` for anonymous callers.

    Returns:
        The user's id when authenticated, otherwise ``"student_default"``.
    """
    return user.id if user else "student_default"


class DreamReport(BaseModel):
    """Result of a dreaming pass returned by ``POST /dream``."""

    sessions_count: int
    reflection_excerpt: str
    misconceptions: list[str]
    next_focus: list[str]
    graph_changes: dict
    files_updated: list[str]


@router.post("", response_model=DreamReport)
async def run_dream(
    db: AsyncSession = Depends(get_db),
    user: UserTable = Depends(get_current_user),
) -> DreamReport:
    """Run a dreaming pass over the caller's recent sessions.

    Loads the most recent sessions (with their messages) for the current
    student, runs the :class:`DreamingService` to reflect on them, writes
    memory files, augments the Knowledge Forge graph, and returns a report.

    Args:
        db: Async database session (injected).
        user: Authenticated user, or ``None`` for anonymous callers (injected).

    Returns:
        A :class:`DreamReport` summarising the dreaming pass.
    """
    sid = _student_id(user)
    q = (
        select(SessionTable)
        .options(selectinload(SessionTable.messages))
        .where(SessionTable.user_id == (user.id if user else None))
        .order_by(SessionTable.updated_at.desc())
        .limit(10)
    )
    rows = (await db.execute(q)).scalars().all()
    svc = await get_orchestrator_service()
    from backend.app.api.v1.knowledge import get_graph
    from backend.app.services.dreaming_service import DreamingService

    dreamer = DreamingService(llm=svc._llm_client, graph=get_graph())

    # dream_from_rows runs a blocking LLM generate() plus file writes and
    # graph.save(). Offload it to a worker thread so the dreaming pass does not
    # freeze the asyncio event loop (same pattern as knowledge._run_extraction).
    def _sync_dream() -> dict:
        return dreamer.dream_from_rows(sid, rows)

    loop = asyncio.get_running_loop()
    report = await loop.run_in_executor(None, _sync_dream)
    return DreamReport(**report)


@router.get("/memory")
async def get_memory(user: UserTable = Depends(get_current_user)) -> dict:
    """Read the caller's stored dreaming memory (profile + reflections).

    Args:
        user: Authenticated caller; anonymous requests get 401 from the
            ``get_current_user`` dependency before this handler runs.

    Returns:
        A dict with the student's ``profile`` text and up to 20 recent
        ``dreams`` (each ``{"name", "content"}``).
    """
    mem = StudentMemoryFiles(_student_id(user))
    dreams = mem.list_dreams()
    return {
        "profile": mem.read_profile(),
        "dreams": [{"name": n, "content": mem.read(n)} for n in dreams[:20]],
    }
