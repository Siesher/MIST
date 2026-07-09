from backend.app.services.session_signals import (
    normalize_topic,
    parse_task_json,
    resolve_topic,
)


class _Row:
    def __init__(self, topic=None, task_json=None):
        self.topic = topic
        self.task_json = task_json


def test_parse_task_json_variants():
    assert parse_task_json(None) == {}
    assert parse_task_json("not json") == {}
    assert parse_task_json('{"problem": "x"}') == {"problem": "x"}
    assert parse_task_json({"problem": "y"}) == {"problem": "y"}
    assert parse_task_json("[1,2]") == {}  # non-object JSON → {}


def test_resolve_topic_precedence():
    assert resolve_topic(_Row(topic="derivatives")) == "derivatives"
    assert resolve_topic(_Row(task_json='{"topic": "limits"}')) == "limits"
    assert resolve_topic(_Row(task_json='{"subject": "physics"}')) == "physics"
    assert resolve_topic(_Row()) == "general"


def test_normalize_topic():
    assert normalize_topic("Linear Equations") == "linear_equations"
    assert normalize_topic(" derivative-rules ") == "derivative_rules"
