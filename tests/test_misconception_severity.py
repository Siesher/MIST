"""Contract for misconception severity parsing (rank-1 quick-win fix).

Defines the behavior `rag_retriever._parse_severity` must satisfy. The regression
and range/passthrough tests pass with the default; the ordering test goes green
only once the human fills the label→weight mapping in `_parse_severity`.
"""

from src.knowledge.rag_retriever import Misconception, _parse_severity


def test_string_severity_does_not_crash():
    # Regression: the data file stores "severity": "high"; the old code did
    # float("high") which raised ValueError and degraded every misconception.
    m = Misconception.from_dict({"id": "x", "topic": "algebra", "severity": "high"})
    assert isinstance(m.severity, float)


def test_severity_within_unit_range():
    for label in ("high", "medium", "low", "definitely-unknown"):
        v = _parse_severity(label)
        assert 0.0 <= v <= 1.0, f"{label!r} -> {v} outside [0, 1]"


def test_severity_labels_strictly_ordered():
    assert _parse_severity("high") > _parse_severity("medium") > _parse_severity("low")


def test_numeric_severity_passthrough_and_clamped():
    assert _parse_severity(0.7) == 0.7
    assert _parse_severity(1.5) == 1.0
    assert _parse_severity(-2) == 0.0
