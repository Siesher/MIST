# tests/test_mastery_service.py
from datetime import datetime

from backend.app.services.mastery_service import (
    MasterySignal,
    compute_mastery,
    mastery_by_skill,
)


class _Msg:
    def __init__(self, is_correct=None, ts=None):
        self.is_correct = is_correct
        self.timestamp = ts or datetime(2026, 5, 31, 12, 0, 0)


class _Row:
    def __init__(self, topic, messages, is_solved=False, attempts=0):
        self.topic = topic
        self.task_json = None
        self.messages = messages
        self.is_solved = is_solved
        self.attempts = attempts
        self.created_at = datetime(2026, 5, 31, 11, 0, 0)
        self.updated_at = datetime(2026, 5, 31, 12, 0, 0)


def test_correct_answers_raise_mastery_above_prior():
    # Three correct graded turns on one topic → p_known well above the 0.3 prior.
    rows = [_Row("derivatives", [_Msg(is_correct=True) for _ in range(3)])]
    signals = compute_mastery(rows)
    assert len(signals) == 1
    s = signals[0]
    assert s.topic == "derivatives"
    assert s.attempts == 3
    assert s.correct == 3
    assert s.p_known > 0.5  # BKT learning pushes it up


def test_incorrect_lowers_relative_to_all_correct():
    high = compute_mastery([_Row("t", [_Msg(is_correct=True) for _ in range(3)])])[0].p_known
    mixed = compute_mastery(
        [_Row("t", [_Msg(is_correct=True), _Msg(is_correct=False), _Msg(is_correct=True)])]
    )[0].p_known
    assert mixed < high


def test_session_level_fallback_when_no_graded_messages():
    # No per-message is_correct, but the session was solved → one positive outcome.
    rows = [_Row("limits", [_Msg(is_correct=None)], is_solved=True)]
    signals = compute_mastery(rows)
    assert len(signals) == 1
    assert signals[0].topic == "limits"
    assert signals[0].attempts == 1
    assert signals[0].p_known > 0.3


def test_empty_rows_yield_no_signals():
    assert compute_mastery([]) == []


def test_mastery_by_skill_maps_topic_to_p_known():
    signals = [MasterySignal(topic="a", p_known=0.7, attempts=2, correct=2)]
    assert mastery_by_skill(signals) == {"a": 0.7}
