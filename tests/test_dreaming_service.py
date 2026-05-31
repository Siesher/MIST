# tests/test_dreaming_service.py
import json

from backend.app.services.dreaming_service import DreamingService, _digest_from_rows


class _Row:
    def __init__(self, topic, is_solved, messages):
        self.id = "s1"
        self.topic = topic
        self.is_solved = is_solved
        self.hints_used = 1
        self.messages = messages


class _Msg:
    def __init__(self, role, content, move_type=None, is_correct=None):
        self.role = role
        self.content = content
        self.move_type = move_type
        self.is_correct = is_correct


def test_digest_from_rows():
    rows = [
        _Row("integrals", True, [_Msg("user", "x^2 dx"), _Msg("tutor", "верно", "encourage", True)])
    ]
    digests = _digest_from_rows(rows)
    assert digests[0].topic == "integrals"
    assert digests[0].solved is True


def test_dream_writes_memory_and_report(tmp_path):
    class _FakeLLM:
        def generate(self, prompt, system=None, **kw):
            return json.dumps(
                {
                    "reflection_md": "## ok",
                    "misconceptions": ["m1"],
                    "next_focus": ["t1"],
                    "profile_update_md": "p",
                }
            )

    rows = [_Row("integrals", True, [_Msg("user", "hi"), _Msg("tutor", "ok")])]
    svc = DreamingService(llm=_FakeLLM(), base_dir=tmp_path, graph=None)
    report = svc.dream_from_rows("alice", rows)
    assert report["sessions_count"] == 1
    assert report["reflection_excerpt"]
    assert report["files_updated"]
