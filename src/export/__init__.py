"""
MITS Export Module

Provides export/import functionality:
- JSON: Full profile export/import
- Obsidian: Markdown vault with wiki-links
- Notion: Database structure export (future)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

__all__ = [
    "ExportFormat",
    "ExportedProfile",
    "EXPORT_VERSION",
]

EXPORT_VERSION = "1.0"


@dataclass
class ExportedProfile:
    """Exported profile structure."""
    version: str
    exported_at: datetime
    student_id: str

    # Core data
    mastery: Dict[str, float]  # topic -> mastery level

    # Gamification
    xp: int
    level: int
    achievements: List[str]  # achievement IDs
    streak_current: int
    streak_longest: int

    # Spaced repetition
    review_cards: List[Dict[str, Any]]

    # Activity
    total_problems: int
    total_time_hours: float
    first_activity: Optional[datetime]
    last_activity: Optional[datetime]

    # Preferences
    preferences: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "version": self.version,
            "exported_at": self.exported_at.isoformat(),
            "profile": {
                "student_id": self.student_id,
                "mastery": self.mastery,
                "gamification": {
                    "xp": self.xp,
                    "level": self.level,
                    "achievements": self.achievements,
                    "streak": {
                        "current": self.streak_current,
                        "longest": self.streak_longest,
                    }
                },
                "spaced_repetition": self.review_cards,
                "activity_summary": {
                    "total_problems": self.total_problems,
                    "total_time_hours": self.total_time_hours,
                    "first_activity": self.first_activity.isoformat() if self.first_activity else None,
                    "last_activity": self.last_activity.isoformat() if self.last_activity else None,
                },
                "preferences": self.preferences,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportedProfile":
        """Create from dictionary (JSON import)."""
        profile = data.get("profile", {})
        gamification = profile.get("gamification", {})
        streak = gamification.get("streak", {})
        activity = profile.get("activity_summary", {})

        return cls(
            version=data.get("version", EXPORT_VERSION),
            exported_at=datetime.fromisoformat(data.get("exported_at", datetime.now().isoformat())),
            student_id=profile.get("student_id", ""),
            mastery=profile.get("mastery", {}),
            xp=gamification.get("xp", 0),
            level=gamification.get("level", 1),
            achievements=gamification.get("achievements", []),
            streak_current=streak.get("current", 0),
            streak_longest=streak.get("longest", 0),
            review_cards=profile.get("spaced_repetition", []),
            total_problems=activity.get("total_problems", 0),
            total_time_hours=activity.get("total_time_hours", 0.0),
            first_activity=datetime.fromisoformat(activity["first_activity"]) if activity.get("first_activity") else None,
            last_activity=datetime.fromisoformat(activity["last_activity"]) if activity.get("last_activity") else None,
            preferences=profile.get("preferences", {}),
        )


class ExportFormat:
    """Supported export formats."""
    JSON = "json"
    OBSIDIAN = "obsidian"
    NOTION = "notion"
