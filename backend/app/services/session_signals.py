# backend/app/services/session_signals.py
"""Shared helpers to read learning signals from stored session rows.

Used by both the dreaming reflection digest and the mastery service so topic
resolution stays identical across them (no drift).
"""

from __future__ import annotations

import json
from typing import Any


def parse_task_json(task_json: Any) -> dict:
    """Parse a session's ``task_json`` column into a dict (best-effort)."""
    if not task_json:
        return {}
    if isinstance(task_json, dict):
        return task_json
    try:
        data = json.loads(task_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_topic(row: Any) -> str:
    """Best topic label: explicit ``topic`` → task ``topic`` → ``subject`` → ``"general"``."""
    task = parse_task_json(getattr(row, "task_json", None))
    topic = getattr(row, "topic", None) or task.get("topic") or task.get("subject") or "general"
    return str(topic)


def normalize_topic(topic: str) -> str:
    """Canonical key for matching a topic against graph node-id slugs."""
    return topic.strip().lower().replace(" ", "_").replace("-", "_")
