"""Analytics aggregation service for student dashboard."""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.tables import SessionTable, MessageTable

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Aggregates student performance data for dashboard visualizations."""

    async def get_activity(
        self, db: AsyncSession, user_id: str, days: int = 90
    ) -> List[Dict[str, Any]]:
        """Get daily activity counts for heatmap."""
        since = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(
                func.date(MessageTable.timestamp).label("day"),
                func.count(MessageTable.id).label("count"),
            )
            .join(SessionTable, MessageTable.session_id == SessionTable.id)
            .where(SessionTable.user_id == user_id, MessageTable.timestamp >= since)
            .group_by(func.date(MessageTable.timestamp))
            .order_by(func.date(MessageTable.timestamp))
        )
        return [{"date": str(row.day), "count": row.count} for row in result.all()]

    async def get_performance(
        self, db: AsyncSession, user_id: str
    ) -> Dict[str, Any]:
        """Get overall performance stats."""
        result = await db.execute(
            select(SessionTable).where(SessionTable.user_id == user_id)
        )
        sessions = result.scalars().all()

        total = len(sessions)
        solved = sum(1 for s in sessions if s.is_solved)
        total_attempts = sum(s.attempts for s in sessions)
        total_hints = sum(s.hints_used for s in sessions)

        return {
            "total_sessions": total,
            "solved_sessions": solved,
            "solve_rate": solved / total if total else 0,
            "total_attempts": total_attempts,
            "total_hints_used": total_hints,
            "avg_attempts_per_session": total_attempts / total if total else 0,
        }

    async def get_mastery_by_topic(
        self, db: AsyncSession, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get mastery level per topic over time."""
        result = await db.execute(
            select(SessionTable)
            .where(SessionTable.user_id == user_id, SessionTable.topic.isnot(None))
            .order_by(SessionTable.created_at)
        )
        sessions = result.scalars().all()

        topic_history = defaultdict(list)
        for s in sessions:
            if s.topic:
                mastery = 1.0 if s.is_solved else max(0.1, 1 - s.attempts * 0.1)
                topic_history[s.topic].append({
                    "date": s.created_at.isoformat() if s.created_at else "",
                    "mastery": mastery,
                })

        return [
            {"topic": topic, "history": points}
            for topic, points in topic_history.items()
        ]

    async def get_error_distribution(
        self, db: AsyncSession, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get error type distribution from messages."""
        result = await db.execute(
            select(MessageTable)
            .join(SessionTable, MessageTable.session_id == SessionTable.id)
            .where(
                SessionTable.user_id == user_id,
                MessageTable.role == "assistant",
                MessageTable.move_type.isnot(None),
            )
        )
        messages = result.scalars().all()

        move_counts = Counter(m.move_type for m in messages if m.move_type)
        total = sum(move_counts.values())

        return [
            {"type": move, "count": count, "percentage": count / total if total else 0}
            for move, count in move_counts.most_common()
        ]

    async def get_recommendations(
        self, db: AsyncSession, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get ZPD-based topic recommendations."""
        result = await db.execute(
            select(SessionTable)
            .where(SessionTable.user_id == user_id, SessionTable.topic.isnot(None))
            .order_by(SessionTable.created_at.desc())
        )
        sessions = result.scalars().all()

        # Calculate per-topic stats
        topic_stats = defaultdict(lambda: {"attempts": 0, "solved": 0, "total": 0})
        for s in sessions:
            if s.topic:
                stats = topic_stats[s.topic]
                stats["total"] += 1
                stats["attempts"] += s.attempts
                if s.is_solved:
                    stats["solved"] += 1

        recommendations = []
        for topic, stats in topic_stats.items():
            solve_rate = stats["solved"] / stats["total"] if stats["total"] else 0

            # ZPD: topics where student struggles but has some success
            if 0.2 <= solve_rate <= 0.7:
                priority = "high"
                reason = "В зоне ближайшего развития"
            elif solve_rate < 0.2:
                priority = "medium"
                reason = "Требует дополнительной практики"
            else:
                priority = "low"
                reason = "Хорошо освоено"

            recommendations.append({
                "topic": topic,
                "priority": priority,
                "reason": reason,
                "solve_rate": solve_rate,
                "sessions": stats["total"],
            })

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_order.get(r["priority"], 3))

        return recommendations


_analytics_service: Optional[AnalyticsService] = None


async def get_analytics_service() -> AnalyticsService:
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
