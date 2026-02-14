"""Main API v1 router."""

from fastapi import APIRouter

from backend.app.api.v1 import auth, sessions, chat, tasks, students, websocket, vision, experiments, analytics, export

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(sessions.router)
router.include_router(chat.router)
router.include_router(tasks.router)
router.include_router(students.router)
router.include_router(websocket.router)
router.include_router(vision.router)
router.include_router(experiments.router)
router.include_router(analytics.router)
router.include_router(export.router)
