"""
MITS Spaced Repetition Module

Implements the SM-2 (SuperMemo 2) algorithm for optimal review scheduling.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

__all__ = [
    "ReviewCard",
    "SM2Result",
    "calculate_sm2",
    "get_next_review_date",
]


@dataclass
class ReviewCard:
    """Represents a review card with SM-2 parameters."""
    id: str
    student_id: str
    topic: str
    easiness_factor: float = 2.5
    interval: int = 1  # days
    repetitions: int = 0
    next_review_date: Optional[date] = None
    last_review_date: Optional[date] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.next_review_date is None:
            self.next_review_date = date.today()
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def is_due(self) -> bool:
        """Check if the card is due for review."""
        return self.next_review_date <= date.today()

    @property
    def days_until_due(self) -> int:
        """Days until the card is due (negative if overdue)."""
        return (self.next_review_date - date.today()).days


@dataclass
class SM2Result:
    """Result of SM-2 calculation."""
    easiness_factor: float
    interval: int
    repetitions: int
    next_review_date: date


def calculate_sm2(
    quality: int,
    easiness_factor: float = 2.5,
    interval: int = 1,
    repetitions: int = 0,
    min_easiness: float = 1.3
) -> SM2Result:
    """
    Calculate the next review parameters using SM-2 algorithm.

    Args:
        quality: Rating from 0-5 (0=complete failure, 5=perfect recall)
        easiness_factor: Current easiness factor (default 2.5)
        interval: Current interval in days
        repetitions: Number of successful repetitions
        min_easiness: Minimum easiness factor (default 1.3)

    Returns:
        SM2Result with new parameters
    """
    # Ensure quality is in valid range
    quality = max(0, min(5, quality))

    # Calculate new easiness factor
    new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(min_easiness, new_ef)

    if quality >= 3:
        # Successful recall
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval * new_ef)
        new_repetitions = repetitions + 1
    else:
        # Failed recall - reset
        new_interval = 1
        new_repetitions = 0

    next_date = date.today() + timedelta(days=new_interval)

    return SM2Result(
        easiness_factor=round(new_ef, 2),
        interval=new_interval,
        repetitions=new_repetitions,
        next_review_date=next_date
    )


def get_next_review_date(interval: int) -> date:
    """Get the next review date based on interval."""
    return date.today() + timedelta(days=interval)
