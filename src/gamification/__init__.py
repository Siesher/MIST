"""
MITS Gamification Module

Provides gamification features:
- XP System: Experience points and level progression
- Achievements: Unlockable badges and milestones
- Streaks: Daily practice tracking
- Levels: Progression system with rewards
"""

from typing import Optional

__all__ = [
    "XPSystem",
    "AchievementManager",
    "StreakTracker",
    "LevelManager",
]


# Level thresholds (XP required for each level)
LEVEL_THRESHOLDS = [
    0,      # Level 1
    100,    # Level 2
    300,    # Level 3
    600,    # Level 4
    1000,   # Level 5
    1500,   # Level 6
    2100,   # Level 7
    2800,   # Level 8
    3600,   # Level 9
    4500,   # Level 10
    5500,   # Level 11
    6600,   # Level 12
    7800,   # Level 13
    9100,   # Level 14
    10500,  # Level 15
    12000,  # Level 16
    13600,  # Level 17
    15300,  # Level 18
    17100,  # Level 19
    19000,  # Level 20
]


# XP rewards for different actions
XP_REWARDS = {
    "problem_solved_easy": 10,
    "problem_solved_medium": 25,
    "problem_solved_hard": 50,
    "problem_solved_olympiad": 100,
    "no_hints_bonus": 10,
    "first_attempt_bonus": 15,
    "review_completed": 5,
    "streak_bonus_per_day": 5,
}


def calculate_level(total_xp: int) -> int:
    """Calculate level from total XP."""
    for level, threshold in enumerate(LEVEL_THRESHOLDS, start=1):
        if total_xp < threshold:
            return level - 1
    return len(LEVEL_THRESHOLDS)


def xp_for_next_level(current_level: int) -> Optional[int]:
    """Get XP required for next level."""
    if current_level >= len(LEVEL_THRESHOLDS):
        return None
    return LEVEL_THRESHOLDS[current_level]


def xp_progress_in_level(total_xp: int, current_level: int) -> tuple[int, int]:
    """Get (current_xp_in_level, xp_needed_for_level)."""
    if current_level >= len(LEVEL_THRESHOLDS):
        return (0, 0)

    level_start = LEVEL_THRESHOLDS[current_level - 1] if current_level > 1 else 0
    level_end = LEVEL_THRESHOLDS[current_level]

    current_in_level = total_xp - level_start
    needed = level_end - level_start

    return (current_in_level, needed)
