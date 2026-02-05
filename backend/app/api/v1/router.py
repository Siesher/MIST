"""Main API v1 router."""

from fastapi import APIRouter

from backend.app.api.v1 import sessions, chat, tasks, students, websocket

router = APIRouter(prefix="/api/v1")

router.include_router(sessions.router)
router.include_router(chat.router)
router.include_router(tasks.router)
router.include_router(students.router)
router.include_router(websocket.router)
