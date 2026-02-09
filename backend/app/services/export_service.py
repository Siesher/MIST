"""
Export service for generating PDF progress reports.

Gathers student data, renders Jinja2 template, converts to PDF with WeasyPrint.
"""

import io
import base64
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class ExportService:
    """Generates PDF progress reports for students."""

    def __init__(self):
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    async def generate_report_pdf(
        self,
        db: AsyncSession,
        user_id: str,
        user_name: str = "Студент",
    ) -> bytes:
        """
        Generate a PDF report for a student.

        Returns PDF content as bytes.
        """
        # Gather data from analytics service
        try:
            from backend.app.services.analytics_service import get_analytics_service
            analytics = await get_analytics_service()

            performance = await analytics.get_performance(db, user_id)
            mastery_raw = await analytics.get_mastery_by_topic(db, user_id)
            error_raw = await analytics.get_error_distribution(db, user_id)
            recommendations = await analytics.get_recommendations(db, user_id)
        except Exception as e:
            logger.error(f"Failed to gather analytics for export: {e}")
            performance = {}
            mastery_raw = []
            error_raw = []
            recommendations = []

        # Get recent sessions
        try:
            from backend.app.services.orchestrator_service import get_orchestrator_service
            orchestrator = await get_orchestrator_service()
            sessions_data = await orchestrator.list_sessions(db, page=1, limit=20, user_id=user_id)
            sessions = [
                {
                    "date": s.created_at.strftime("%d.%m.%Y"),
                    "topic": s.topic,
                    "mode": s.mode,
                    "is_solved": s.is_solved,
                    "hints_used": s.hints_used,
                }
                for s in sessions_data.get("sessions", [])
            ]
        except Exception as e:
            logger.warning(f"Failed to get sessions for export: {e}")
            sessions = []

        # Prepare mastery data for template
        mastery_data = []
        for item in mastery_raw:
            topic = item.get("topic", "")
            history = item.get("history", [])
            latest = history[-1]["mastery"] if history else 0
            mastery_data.append({
                "topic": topic,
                "mastery": round(latest * 100),
            })

        # Prepare error data
        error_data = [
            {
                "type": _interaction_label(e.get("type", "")),
                "count": e.get("count", 0),
                "percentage": round(e.get("percentage", 0) * 100),
            }
            for e in error_raw
        ]

        # Generate mastery chart image
        mastery_chart_img = self._render_mastery_chart(mastery_data)

        # Build template context
        context = {
            "student_name": user_name,
            "report_date": datetime.utcnow().strftime("%d.%m.%Y"),
            "total_sessions": performance.get("total_sessions", 0),
            "solved_sessions": performance.get("solved_sessions", 0),
            "solve_rate": round(performance.get("solve_rate", 0) * 100),
            "total_hints": performance.get("total_hints_used", 0),
            "mastery_data": mastery_data,
            "mastery_chart_img": mastery_chart_img,
            "error_data": error_data,
            "sessions": sessions[:15],
            "recommendations": recommendations,
        }

        # Render HTML
        template = self._jinja_env.get_template("report.html")
        html_content = template.render(**context)

        # Convert to PDF
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes
        except ImportError:
            logger.warning("WeasyPrint not installed, returning HTML as fallback")
            return html_content.encode("utf-8")

    def _render_mastery_chart(self, mastery_data: List[Dict[str, Any]]) -> Optional[str]:
        """Render mastery chart as base64 PNG using matplotlib."""
        if not mastery_data:
            return None

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            topics = [d["topic"] for d in mastery_data]
            values = [d["mastery"] for d in mastery_data]
            colors = ["#e2725b" if v >= 70 else "#1976d2" if v >= 40 else "#999" for v in values]

            fig, ax = plt.subplots(figsize=(8, max(2, len(topics) * 0.5)))
            bars = ax.barh(topics, values, color=colors, height=0.6)
            ax.set_xlim(0, 100)
            ax.set_xlabel("Уровень освоения (%)")
            ax.invert_yaxis()

            for bar, val in zip(bars, values):
                ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                        f"{val}%", va="center", fontsize=9)

            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("ascii")

        except ImportError:
            logger.info("matplotlib not available for chart rendering")
            return None


def _interaction_label(type_key: str) -> str:
    """Map interaction type to Russian label."""
    labels = {
        "scaffolding": "Направление",
        "hint": "Подсказки",
        "encourage": "Поощрение",
        "rectify": "Исправление",
        "tell": "Прямой ответ",
    }
    return labels.get(type_key, type_key)


# Singleton
_export_service: Optional[ExportService] = None


async def get_export_service() -> ExportService:
    """Get or create the export service singleton."""
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service
