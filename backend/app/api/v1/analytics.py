"""Analytics API endpoints for student dashboard and performance metrics."""

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.database import get_db
from backend.app.services.analytics_service import get_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/metrics")
async def get_performance_metrics():
    """Report cache hit rate, avg latency, and optimization stats."""
    metrics: dict = {}

    # LLM response cache stats
    try:
        from backend.app.services.cache_service import get_cache_service
        metrics["llm_cache"] = get_cache_service().stats
    except Exception:
        metrics["llm_cache"] = None

    # Hint prefetcher stats
    try:
        from src.inference.hint_prefetcher import get_hint_prefetcher
        metrics["hint_prefetcher"] = get_hint_prefetcher().stats
    except Exception:
        metrics["hint_prefetcher"] = None

    # Context compressor settings
    try:
        from src.inference.context_compressor import get_context_compressor
        metrics["context_compressor"] = get_context_compressor().get_stats()
    except Exception:
        metrics["context_compressor"] = None

    # Response cache (semantic) stats
    try:
        from src.inference.cache import get_cache_manager
        metrics["semantic_cache"] = get_cache_manager().get_stats()
    except Exception:
        metrics["semantic_cache"] = None

    # Inference metrics (latency tracking)
    try:
        from src.inference.metrics import get_metrics_collector
        collector = get_metrics_collector()
        metrics["inference"] = collector.get_model_stats("glm-4.7-flash", hours=24)
    except Exception:
        metrics["inference"] = None

    return metrics


@router.get("/activity")
async def get_activity(
    user_id: str = Query(...),
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get daily activity counts for heatmap visualization."""
    service = await get_analytics_service()
    return await service.get_activity(db, user_id, days)


@router.get("/performance")
async def get_performance(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get overall performance statistics."""
    service = await get_analytics_service()
    return await service.get_performance(db, user_id)


@router.get("/mastery")
async def get_mastery(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get mastery levels per topic over time."""
    service = await get_analytics_service()
    return await service.get_mastery_by_topic(db, user_id)


@router.get("/errors")
async def get_errors(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get error type distribution."""
    service = await get_analytics_service()
    return await service.get_error_distribution(db, user_id)


@router.get("/recommendations")
async def get_recommendations(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get ZPD-based topic recommendations."""
    service = await get_analytics_service()
    return await service.get_recommendations(db, user_id)
