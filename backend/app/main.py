"""
MITS FastAPI Backend

Main entry point for the tutoring API server.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

# Add project root to path for src/ imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import router as api_router
from backend.app.config import backend_settings
from backend.app.models.database import close_db, init_db
from backend.app.services.orchestrator_service import get_orchestrator_service

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if backend_settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup then shutdown (replaces deprecated on_event)."""
    logger.info("Starting MITS API server...")
    await init_db()
    logger.info("Database initialized")
    await get_orchestrator_service()
    logger.info("MITS API server ready")
    yield
    await close_db()
    logger.info("MITS API server shut down")


# Create app (Swagger/ReDoc только в DEBUG — в проде интерактивные доки не светим)
app = FastAPI(
    title="MITS API",
    description="Mathematics Intelligent Tutoring System API",
    version="1.0.0",
    docs_url="/docs" if backend_settings.DEBUG else None,
    redoc_url="/redoc" if backend_settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in backend_settings.CORS_ORIGINS.split(",")]
# Allow temporary public-tunnel origins (Cloudflare Tunnel / ngrok / localtunnel) so a
# one-off public URL works without a redeploy. allow_credentials=True forbids a "*"
# allow_origins, so tunnels are matched by regex instead. Set CORS_ORIGIN_REGEX="" to disable.
cors_origin_regex = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"https://[a-z0-9-]+\.(trycloudflare\.com|ngrok-free\.app|ngrok\.io|loca\.lt)",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


# Health check at root level
@app.get("/api/v1/health")
async def health_check():
    """System health check."""
    service = await get_orchestrator_service()
    return service.get_health()


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    # Echo CORS headers on errors too, so browsers see the real 500 instead of a
    # misleading "No Access-Control-Allow-Origin" (CORS) error masking it.
    import re as _re

    origin = request.headers.get("origin")
    allowed = {o.strip() for o in backend_settings.CORS_ORIGINS.split(",")}
    _rx = os.getenv(
        "CORS_ORIGIN_REGEX",
        r"https://[a-z0-9-]+\.(trycloudflare\.com|ngrok-free\.app|ngrok\.io|loca\.lt)",
    )
    headers: dict[str, str] = {}
    if origin and (origin in allowed or "*" in allowed or (_rx and _re.match(_rx, origin))):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Внутренняя ошибка сервера",
            }
        },
        headers=headers,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
