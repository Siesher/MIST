import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_vstar_pairs as bvp


def _traj(idx, thinking="думаю", content="ответ", correct=True, done_reason="early_boxed"):
    return {
        "sample_idx": idx,
        "thinking": thinking,
        "content": content,
        "correct": correct,
        "done_reason": done_reason,
    }


def test_make_completion_combines_thinking_and_content():
    t = _traj(0, thinking="шаг1", content="итог")
    assert bvp.make_completion(t) == "<think>шаг1</think>\nитог"


def test_make_completion_empty_content():
    t = _traj(0, thinking="долгое", content="")
    assert bvp.make_completion(t) == "<think>долгое</think>\n"


def test_has_content():
    assert bvp.has_content(_traj(0, content="x")) is True
    assert bvp.has_content(_traj(0, content="   ")) is False


def test_build_pair_record_shape():
    row = {"subset_idx": 7, "prompt": "Реши задачу", "domain": "math", "difficulty": "hard"}
    ch = _traj(1, content="хорошо", correct=True)
    rj = _traj(2, content="плохо", correct=False)
    rec = bvp.build_pair_record(row, ch, rj, "A")
    assert rec["pair_id"] == "7__1__2"
    assert rec["prompt"] == [{"role": "user", "content": "Реши задачу"}]
    assert rec["chosen"].startswith("<think>")
    assert rec["strategy"] == "A"
    assert rec["scores_chosen"]["correctness"] == 1.0
    assert rec["scores_rejected"]["correctness"] == 0.0
    assert rec["chosen"] != rec["rejected"]


def test_select_pair_A_prefers_early_boxed_content_chosen():
    # correct: один early_boxed+content (idx0), один length без content (idx1)
    # incorrect: один с content (idx2), один без (idx3)
    row = {
        "trajectories": [
            _traj(0, content="реш", correct=True, done_reason="early_boxed"),
            _traj(1, content="", correct=True, done_reason="length"),
            _traj(2, content="невер", correct=False, done_reason="early_boxed"),
            _traj(3, content="", correct=False, done_reason="length"),
        ]
    }
    ch, rj = bvp.select_pair_A(row)
    assert ch["sample_idx"] == 0  # correct + content + early_boxed
    assert rj["correct"] is False and bvp.has_content(rj)  # incorrect с content
    assert rj["sample_idx"] == 2


def test_select_pair_A_rejected_falls_back_to_truncated():
    # все incorrect без content -> rejected = incorrect (обрезанный)
    row = {
        "trajectories": [
            _traj(0, content="реш", correct=True),
            _traj(1, content="", correct=False, done_reason="length"),
        ]
    }
    ch, rj = bvp.select_pair_A(row)
    assert ch["correct"] is True
    assert rj["correct"] is False


def test_select_pair_B_content_vs_truncated():
    # все correct (4/4), смесь: 2 с content, 2 обрезаны
    row = {
        "trajectories": [
            _traj(0, content="полный1", correct=True, done_reason="early_boxed"),
            _traj(1, content="", correct=True, done_reason="length"),
            _traj(2, content="полный2", correct=True, done_reason="early_boxed"),
            _traj(3, content="", correct=True, done_reason="length"),
        ]
    }
    res = bvp.select_pair_B(row)
    assert res is not None
    ch, rj = res
    assert bvp.has_content(ch) and not bvp.has_content(rj)
    assert ch["sample_idx"] == 0 and rj["sample_idx"] == 1


def test_select_pair_B_none_when_all_content():
    # все correct + все с content -> нет completeness-контраста
    row = {"trajectories": [_traj(i, content="x", correct=True) for i in range(4)]}
    assert bvp.select_pair_B(row) is None


def test_build_all_pairs_strategies():
    rows = [
        # mixed -> A
        {
            "subset_idx": 0,
            "prompt": "p0",
            "domain": "math",
            "difficulty": "hard",
            "n_correct": 2,
            "trajectories": [
                _traj(0, content="c", correct=True),
                _traj(1, content="", correct=False, done_reason="length"),
                _traj(2, content="c", correct=True),
                _traj(3, content="w", correct=False),
            ],
        },
        # 4/4 смесь -> B
        {
            "subset_idx": 1,
            "prompt": "p1",
            "domain": "cs",
            "difficulty": "hard",
            "n_correct": 4,
            "trajectories": [
                _traj(0, content="c", correct=True),
                _traj(1, content="", correct=True, done_reason="length"),
                _traj(2, content="c", correct=True),
                _traj(3, content="c", correct=True),
            ],
        },
        # 0/4 -> пропуск
        {
            "subset_idx": 2,
            "prompt": "p2",
            "domain": "bio",
            "difficulty": "hard",
            "n_correct": 0,
            "trajectories": [_traj(i, content="", correct=False) for i in range(4)],
        },
    ]
    pairs = bvp.build_all_pairs(rows)
    strat = sorted(p["strategy"] for p in pairs)
    assert strat == ["A", "B"]  # 0/4 пропущен
    assert all(p["chosen"] for p in pairs)
    assert len({p["pair_id"] for p in pairs}) == 2


def test_build_pair_record_handles_none_correct():
    # реальные данные: correct=None (верификация неоднозначна) -> трактуем как 0.0
    row = {"subset_idx": 0, "prompt": "p", "domain": "math", "difficulty": "hard"}
    ch = _traj(0, content="ok", correct=True)
    rj = _traj(1, content="x", correct=None)
    rec = bvp.build_pair_record(row, ch, rj, "A")
    assert rec["scores_rejected"]["correctness"] == 0.0
    assert rec["scores_chosen"]["correctness"] == 1.0
