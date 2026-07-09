"""Inference metrics + cache stats — observability endpoints.

Aggregates:
  * LLMCacheService (backend/app/services/cache_service.py) — hit rate, size
  * src/inference/metrics.py MetricsCollector — recent tok/s, latencies

Read-only, кроме POST /cache/clear (admin/debug, требует авторизации).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.api.v1.auth import get_current_user
from backend.app.models.tables import UserTable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


METRICS_DB = Path("backend/data/inference_metrics.db")


class CacheStats(BaseModel):
    size: int
    max_size: int
    ttl_seconds: int
    hits: int
    misses: int
    hit_rate: float
    total_requests: int


class InferenceSummary(BaseModel):
    total_requests: int
    avg_ttft_ms: float | None
    avg_tok_per_sec: float | None
    avg_total_ms: float | None
    p50_tok_per_sec: float | None
    p95_tok_per_sec: float | None
    recent_errors: int


class MetricsSnapshot(BaseModel):
    cache: CacheStats
    inference: InferenceSummary


def _load_inference_summary() -> InferenceSummary:
    empty = InferenceSummary(
        total_requests=0,
        avg_ttft_ms=None,
        avg_tok_per_sec=None,
        avg_total_ms=None,
        p50_tok_per_sec=None,
        p95_tok_per_sec=None,
        recent_errors=0,
    )
    if not METRICS_DB.exists():
        return empty

    try:
        with sqlite3.connect(METRICS_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    COUNT(*),
                    AVG(time_to_first_token_ms),
                    AVG(tokens_per_second),
                    AVG(total_generation_time_ms),
                    SUM(CASE WHEN had_error=1 THEN 1 ELSE 0 END)
                FROM inference_metrics
                WHERE timestamp >= datetime('now', '-24 hours')
                """
            )
            total, ttft, tps, total_ms, errs = cur.fetchone()

            # Percentiles via window
            cur.execute(
                """
                SELECT tokens_per_second FROM inference_metrics
                WHERE tokens_per_second IS NOT NULL AND timestamp >= datetime('now', '-24 hours')
                ORDER BY tokens_per_second
                """
            )
            vals = [r[0] for r in cur.fetchall()]
            p50 = vals[len(vals) // 2] if vals else None
            p95 = vals[int(len(vals) * 0.95)] if vals else None

            return InferenceSummary(
                total_requests=total or 0,
                avg_ttft_ms=ttft,
                avg_tok_per_sec=tps,
                avg_total_ms=total_ms,
                p50_tok_per_sec=p50,
                p95_tok_per_sec=p95,
                recent_errors=errs or 0,
            )
    except Exception as e:
        logger.warning(f"metrics DB read failed: {e}")
        return empty


@router.get("", response_model=MetricsSnapshot)
async def get_metrics() -> MetricsSnapshot:
    """Full metrics snapshot: cache stats + inference summary over last 24h."""
    from backend.app.services.cache_service import get_cache_service

    cache = get_cache_service()
    cache_stats = CacheStats(**cache.stats)

    return MetricsSnapshot(cache=cache_stats, inference=_load_inference_summary())


@router.get("/cache", response_model=CacheStats)
async def get_cache_stats() -> CacheStats:
    """Cache-only stats (fast endpoint, no DB hit)."""
    from backend.app.services.cache_service import get_cache_service

    return CacheStats(**get_cache_service().stats)


@router.post("/cache/clear")
async def clear_cache(user: UserTable = Depends(get_current_user)) -> dict[str, Any]:
    """Clear LLM response cache (admin/debug) — только для авторизованных."""
    from backend.app.services.cache_service import get_cache_service

    before = get_cache_service().stats["size"]
    get_cache_service().clear()
    return {"cleared": before}


# ─────────────────────────────────────────────────────────────────────
# Agent chain tracing
# ─────────────────────────────────────────────────────────────────────


@router.get("/traces")
async def list_traces(limit: int = 20, user: UserTable = Depends(get_current_user)) -> dict[str, Any]:
    """Recent session IDs with trace summary stats."""
    from backend.app.services.tracing import get_tracer

    tracer = get_tracer()
    session_ids = tracer.get_recent_sessions(limit=limit)
    sessions = []
    for sid in session_ids:
        spans = tracer.get_traces(sid)
        if not spans:
            continue
        total_ms = sum(s.get("duration_ms") or 0 for s in spans if s.get("parent_id") is None)
        errors = sum(1 for s in spans if s.get("status") == "error")
        sessions.append(
            {
                "session_id": sid,
                "span_count": len(spans),
                "total_ms": round(total_ms, 1),
                "errors": errors,
                "stage_names": sorted({s["name"] for s in spans if s.get("parent_id") is None}),
            }
        )
    return {"sessions": sessions, "summary": tracer.summary()}


@router.get("/traces/{session_id}")
async def get_session_traces(session_id: str, user: UserTable = Depends(get_current_user)) -> dict[str, Any]:
    """Full trace for a session: tree of spans with timings + attributes."""
    from backend.app.services.tracing import get_tracer

    spans = get_tracer().get_traces(session_id)
    if not spans:
        return {"session_id": session_id, "spans": [], "found": False}
    return {"session_id": session_id, "spans": spans, "found": True, "span_count": len(spans)}
