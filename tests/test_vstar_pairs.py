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
