"""Lightweight agent-chain tracer — no OTel, just Python context managers.

Gives you per-session timing spans for:
    Profiler → Planner → ToM → Tutor → Verifier
plus nested spans for cache checks, LLM calls, graph queries.

Traces are stored in-memory (ring buffer, last 100 sessions) and surfaced via
`/api/v1/metrics/traces/{session_id}` for UI inspection. For production you'd
swap in OpenTelemetry; this API is compatible.

Usage:
    with tracer.span("profiler", session_id=sid, correlation_id=cid) as sp:
        level = profiler.profile(msg)
        sp.set_attr("student.level", level)
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Iterator

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────


@dataclass
class Span:
    """One trace span — a single timed step in the agent chain."""

    span_id: str
    name: str
    session_id: str
    correlation_id: str
    parent_id: str | None
    start_ms: float
    end_ms: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"  # ok | error | cancelled
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        if self.end_ms is None:
            return None
        return self.end_ms - self.start_ms

    def set_attr(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, **attrs: Any) -> None:
        self.events.append({"name": name, "ts_ms": time.perf_counter() * 1000, **attrs})

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "name": self.name,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "parent_id": self.parent_id,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "attributes": self.attributes,
            "events": self.events,
        }


# ─────────────────────────────────────────────────────────────────────
# Tracer singleton
# ─────────────────────────────────────────────────────────────────────


class Tracer:
    """Thread-safe in-memory tracer with per-session ring buffer.

    Each session accumulates spans under its correlation_id. When a session
    has no activity for max_idle_s, it gets flushed to the completed buffer.
    Completed sessions are evicted when count exceeds max_completed.
    """

    def __init__(self, max_completed: int = 100):
        self._max_completed = max_completed
        # session_id -> list[Span]
        self._active: dict[str, list[Span]] = {}
        self._completed: OrderedDict[str, list[Span]] = OrderedDict()
        # Stack of current spans per session (for parent_id resolution)
        self._stack: dict[str, list[str]] = {}
        self._lock = RLock()

        self.stats = {
            "spans_started": 0,
            "spans_completed": 0,
            "spans_errored": 0,
            "sessions_tracked": 0,
        }

    def new_correlation_id(self) -> str:
        """Create a new correlation ID for a conversation turn."""
        return uuid.uuid4().hex[:16]

    @contextmanager
    def span(
        self,
        name: str,
        session_id: str,
        correlation_id: str | None = None,
        **attrs: Any,
    ) -> Iterator[Span]:
        """Start a timed span. Auto-nests under current parent span."""
        corr = correlation_id or self.new_correlation_id()

        with self._lock:
            stack = self._stack.setdefault(session_id, [])
            parent_id = stack[-1] if stack else None
            sp = Span(
                span_id=uuid.uuid4().hex[:16],
                name=name,
                session_id=session_id,
                correlation_id=corr,
                parent_id=parent_id,
                start_ms=time.perf_counter() * 1000,
                attributes=dict(attrs),
            )
            self._active.setdefault(session_id, []).append(sp)
            stack.append(sp.span_id)
            self.stats["spans_started"] += 1

        try:
            yield sp
        except Exception as e:
            with self._lock:
                sp.status = "error"
                sp.error = f"{type(e).__name__}: {e}"
                self.stats["spans_errored"] += 1
            raise
        finally:
            with self._lock:
                sp.end_ms = time.perf_counter() * 1000
                if sp.status == "ok":
                    self.stats["spans_completed"] += 1
                # pop from stack
                if stack and stack[-1] == sp.span_id:
                    stack.pop()
                # log (compact)
                logger.debug(
                    "span.end",
                    extra={
                        "span": sp.name,
                        "session": session_id,
                        "corr": corr,
                        "dur_ms": round(sp.duration_ms or 0, 1),
                        "status": sp.status,
                    },
                )

    def finalize_session(self, session_id: str) -> None:
        """Move active spans to completed buffer (end of session turn)."""
        with self._lock:
            spans = self._active.pop(session_id, None)
            self._stack.pop(session_id, None)
            if not spans:
                return

            if session_id not in self._completed:
                self.stats["sessions_tracked"] += 1
            self._completed[session_id] = spans
            self._completed.move_to_end(session_id)

            # Evict oldest
            while len(self._completed) > self._max_completed:
                self._completed.popitem(last=False)

    def get_traces(self, session_id: str) -> list[dict[str, Any]]:
        """Get all completed spans for a session."""
        with self._lock:
            spans = self._completed.get(session_id, [])
            return [sp.to_dict() for sp in spans]

    def get_recent_sessions(self, limit: int = 20) -> list[str]:
        """Recent session IDs (newest first)."""
        with self._lock:
            return list(reversed(list(self._completed.keys())))[:limit]

    def summary(self) -> dict[str, Any]:
        """Global tracer stats."""
        with self._lock:
            return {
                **self.stats,
                "active_sessions": len(self._active),
                "completed_sessions": len(self._completed),
            }


# ─────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


# ─────────────────────────────────────────────────────────────────────
# Convenience decorator
# ─────────────────────────────────────────────────────────────────────


def traced(span_name: str):
    """Decorator: wrap method to auto-open span.

    Requires first arg (besides self) to be session_id OR the instance to have
    `self._session_id`. Falls through silently if no session context.
    """

    def decorator(fn):
        def wrapper(*args, **kwargs):
            session_id = kwargs.get("session_id")
            if session_id is None and len(args) >= 2:
                maybe_sid = args[1]
                if isinstance(maybe_sid, str) and len(maybe_sid) >= 8:
                    session_id = maybe_sid
            if session_id is None:
                session_id = getattr(args[0], "_session_id", None) if args else None

            if session_id is None:
                return fn(*args, **kwargs)

            with get_tracer().span(span_name, session_id=session_id):
                return fn(*args, **kwargs)

        return wrapper

    return decorator
