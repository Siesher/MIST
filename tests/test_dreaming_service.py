# tests/test_dreaming_service.py
import json

from backend.app.services.dreaming_service import DreamingService, _digest_from_rows


class _Row:
    def __init__(
        self,
        topic,
        is_solved,
        messages,
        row_id="s1",
        task_json=None,
        difficulty=None,
        mode=None,
        attempts=0,
        created_at=None,
        updated_at=None,
    ):
        self.id = row_id
        self.topic = topic
        self.is_solved = is_solved
        self.hints_used = 1
        self.messages = messages
        self.task_json = task_json
        self.difficulty = difficulty
        self.mode = mode
        self.attempts = attempts
        self.created_at = created_at
        self.updated_at = updated_at


class _Msg:
    def __init__(self, role, content, move_type=None, is_correct=None):
        self.role = role
        self.content = content
        self.move_type = move_type
        self.is_correct = is_correct


class _FakeGraph:
    """Records add_node calls and reports configured existing node ids.

    Mirrors the slice of ``KnowledgeGraph`` that ``_augment_graph`` touches:
    ``get_node`` (dedup), ``add_node`` (insert), ``save`` (persist).
    """

    def __init__(self, existing=None):
        self._existing = set(existing or [])
        self.added = []  # list of KnowledgeNode
        self.save_calls = 0

    def get_node(self, node_id):
        if node_id in self._existing:
            return object()  # any non-None marker = "already present"
        return None

    def add_node(self, node):
        self.added.append(node)
        # make subsequent get_node see it (real graph behaviour)
        self._existing.add(node.id)

    def save(self):
        self.save_calls += 1


def _ok_llm(payload):
    class _FakeLLM:
        def generate(self, prompt, system=None, **kw):
            return json.dumps(payload, ensure_ascii=False)

    return _FakeLLM()


def test_digest_from_rows():
    rows = [
        _Row("integrals", True, [_Msg("user", "x^2 dx"), _Msg("tutor", "верно", "encourage", True)])
    ]
    digests = _digest_from_rows(rows)
    assert digests[0].topic == "integrals"
    assert digests[0].solved is True


def test_digest_pulls_problem_difficulty_and_transcript():
    """task_json → real problem/answer/difficulty/subject; messages → marked transcript."""
    task = json.dumps(
        {"problem": "∫ x dx", "answer": "x^2/2 + C", "difficulty": "easy", "subject": "math"},
        ensure_ascii=False,
    )
    row = _Row(
        "integrals",
        False,
        [
            _Msg("user", "x^2/2"),
            _Msg("tutor", "А константа интегрирования?", "probing", False),
            _Msg("user", "x^2/2 + C"),
            _Msg("tutor", "Верно!", "encourage", True),
        ],
        task_json=task,
        mode="guided_learning",
    )
    d = _digest_from_rows([row])[0]
    assert d.problem == "∫ x dx"
    assert d.answer.startswith("x^2/2")
    assert d.difficulty == "easy"  # falls back to task difficulty when row.difficulty is None
    assert d.subject == "math"
    assert d.mode == "guided_learning"
    # transcript renders every message with role + Socratic move + ✓/✗ markers
    assert len(d.transcript) == 4
    assert any(ln.strip().startswith("ученик") for ln in d.transcript)
    assert any("[probing]" in ln and "✗" in ln for ln in d.transcript)
    assert any("[encourage]" in ln and "✓" in ln for ln in d.transcript)


def test_digest_extracts_errors_with_truncation():
    """Only is_correct is False messages become errors; content [:120], list [:5]."""
    long_text = "x" * 200
    msgs = [_Msg("user", "hi")]
    # 6 incorrect messages → must be capped at 5; each content truncated to 120 chars
    msgs += [_Msg("user", long_text, is_correct=False) for _ in range(6)]
    # a correct one and a None-correct one must NOT be harvested as errors
    msgs += [_Msg("tutor", "верно", is_correct=True), _Msg("tutor", "ok", is_correct=None)]
    rows = [_Row("integrals", False, msgs)]

    digests = _digest_from_rows(rows)
    d = digests[0]
    assert d.solved is False
    assert d.hints == 1
    assert d.turns == len(msgs)
    assert len(d.errors) == 5  # capped at 5 despite 6 incorrect messages
    assert all(len(e) == 120 for e in d.errors)  # each truncated to 120 chars


def test_dream_writes_memory_and_report(tmp_path):
    rows = [_Row("integrals", True, [_Msg("user", "hi"), _Msg("tutor", "ok")])]
    svc = DreamingService(
        llm=_ok_llm(
            {
                "reflection_md": "## ok",
                "misconceptions": ["m1"],
                "next_focus": ["t1"],
                "profile_update_md": "p",
            }
        ),
        base_dir=tmp_path,
        graph=None,
    )
    report = svc.dream_from_rows("alice", rows)
    assert report["sessions_count"] == 1
    assert report["reflection_excerpt"]
    assert report["files_updated"]


def test_files_updated_points_at_profile(tmp_path):
    """files_updated reports the profile.md path inside the student's memory dir."""
    rows = [_Row("integrals", True, [_Msg("user", "hi")])]
    svc = DreamingService(llm=_ok_llm({"reflection_md": "## ok"}), base_dir=tmp_path, graph=None)
    report = svc.dream_from_rows("alice", rows)
    assert len(report["files_updated"]) == 1
    profile_path = report["files_updated"][0]
    assert profile_path.endswith("profile.md")
    assert "alice" in profile_path  # scoped to this student


def test_augment_graph_adds_misconception_nodes(tmp_path):
    """The real _augment_graph branch: dedup via get_node, add_node, save once."""
    graph = _FakeGraph()
    svc = DreamingService(
        llm=_ok_llm(
            {
                "reflection_md": "## ok",
                "misconceptions": ["Путает знак при подстановке", "Forgets +C"],
                "next_focus": ["t1"],
                "profile_update_md": "p",
            }
        ),
        base_dir=tmp_path,
        graph=graph,
    )
    report = svc.dream_from_rows("alice", [_Row("integrals", False, [])])

    assert report["graph_changes"] == {"nodes_added": 2}
    assert len(graph.added) == 2
    assert graph.save_calls == 1  # save() called exactly once, only because nodes were added

    from src.knowledge.knowledge_forge import NodeType

    node = graph.added[0]
    assert node.node_type == NodeType.MISCONCEPTION
    assert node.source == "dreaming"
    assert node.domain == "math"
    # slug: lowercased, non-[a-z0-9] collapsed to "_"; ascii-only text yields ascii slug
    assert node.id.startswith("math:dream_")
    assert node.id.endswith(":misconception")
    # cyrillic text has no [a-z0-9] → slug empty → uuid fallback (8 hex chars)
    assert graph.added[0].id != graph.added[1].id


def test_augment_graph_slug_and_caps(tmp_path):
    """misconceptions[:5] cap; slug regex lowercases + collapses; title/content [:80]."""
    long_misconception = "ABC " + "z" * 200  # long, mixed case, spaces
    misconceptions = [long_misconception] + [f"err number {i}" for i in range(6)]  # 7 total
    graph = _FakeGraph()
    svc = DreamingService(
        llm=_ok_llm({"reflection_md": "## ok", "misconceptions": misconceptions}),
        base_dir=tmp_path,
        graph=graph,
    )
    report = svc.dream_from_rows("bob", [_Row("integrals", False, [])])

    assert report["graph_changes"] == {"nodes_added": 5}  # capped at 5 despite 7
    assert len(graph.added) == 5
    first = graph.added[0]
    # title/title_en truncated to 80 chars; content keeps the full text
    assert len(first.title) == 80
    assert len(first.title_en) == 80
    assert first.content == long_misconception  # content is NOT truncated
    # slug lowercased + non-alnum collapsed to "_", capped to 40 chars in the id segment
    slug_segment = first.id[len("math:dream_") : -len(":misconception")]
    assert slug_segment == slug_segment.lower()
    assert " " not in slug_segment
    assert len(slug_segment) <= 40


def test_augment_graph_skips_existing_nodes(tmp_path):
    """get_node returning non-None skips add_node; save() not called when nothing added."""
    misconception = "forgets to add constant"
    slug = "forgets_to_add_constant"
    existing_id = f"math:dream_{slug}:misconception"
    graph = _FakeGraph(existing={existing_id})
    svc = DreamingService(
        llm=_ok_llm({"reflection_md": "## ok", "misconceptions": [misconception]}),
        base_dir=tmp_path,
        graph=graph,
    )
    report = svc.dream_from_rows("carol", [_Row("integrals", False, [])])

    assert report["graph_changes"] == {"nodes_added": 0}
    assert graph.added == []
    assert graph.save_calls == 0  # save() NOT called when nothing was added


def test_augment_graph_noop_without_misconceptions(tmp_path):
    """Empty misconceptions → no get_node/add_node/save at all."""
    graph = _FakeGraph()
    svc = DreamingService(
        llm=_ok_llm({"reflection_md": "## ok", "misconceptions": []}),
        base_dir=tmp_path,
        graph=graph,
    )
    report = svc.dream_from_rows("dave", [_Row("integrals", True, [])])

    assert report["graph_changes"] == {"nodes_added": 0}
    assert graph.added == []
    assert graph.save_calls == 0


def test_sessions_seen_merge_is_idempotent(tmp_path):
    """state.sessions_seen unions across dreams; re-dreaming the same row adds nothing new."""
    llm = _ok_llm({"reflection_md": "## ok", "misconceptions": []})
    base = tmp_path

    row_a = _Row("integrals", True, [_Msg("user", "hi")], row_id="sess-A")
    row_b = _Row("limits", False, [_Msg("user", "lim")], row_id="sess-B")

    DreamingService(llm=llm, base_dir=base, graph=None).dream_from_rows("erin", [row_a])
    DreamingService(llm=llm, base_dir=base, graph=None).dream_from_rows("erin", [row_a, row_b])

    from src.memory.memory_files import StudentMemoryFiles

    state = StudentMemoryFiles("erin", base_dir=base).read_state()
    # set-merge → each id appears exactly once despite row_a being seen twice
    assert sorted(state["sessions_seen"]) == ["sess-A", "sess-B"]
    assert state["last_dreamed_at"]  # timestamp recorded
