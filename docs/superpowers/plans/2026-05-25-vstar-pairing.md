# V-STaR within-task pairing (A+B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить `training/data/vstar_dpo_pairs.jsonl` (~84 within-task DPO-пары) из `vstar_trajectories_hard.jsonl` по стратегиям A (correctness-mixed) + B (completeness в 4/4), без PRM.

**Architecture:** Чистые функции selection (`select_pair_A/B`, `make_completion`, `build_pair_record`) — unit-тестируемы на синтетических траекториях (настоящий TDD). Оркестратор `build_all_pairs` + I/O в `main()`. Формат пар по 019 data-model + conversational prompt (TRL DPOTrainer).

**Tech Stack:** Python 3.11, pytest, stdlib (json). Без внешних ML-зависимостей.

> **Spec:** `docs/superpowers/specs/2026-05-25-vstar-pairing-design.md`

## Структуры данных (из анализа, для справки)
- **row keys:** `subset_idx, prompt, answer, domain, difficulty, source, answer_type, trajectories[N], n_correct, n_total, model`
- **trajectory keys:** `sample_idx, seed, thinking, content, extracted, tokens, elapsed_s, done_reason, correct`

---

## File Structure

| Файл | Ответственность |
|------|-----------------|
| `scripts/build_vstar_pairs.py` | Selection logic (pure fns) + orchestrator + I/O |
| `tests/test_vstar_pairs.py` | Unit-тесты selection logic на синтетике |
| `training/data/vstar_dpo_pairs.jsonl` | Выход (генерируется) |

Тесты импортируют функции через `sys.path.insert(0, scripts/)` → `import build_vstar_pairs`.

---

## Task 1: Helpers — make_completion, has_content, build_pair_record

**Files:**
- Create: `scripts/build_vstar_pairs.py`
- Create: `tests/test_vstar_pairs.py`

- [ ] **Step 1: Написать failing-тесты**

`tests/test_vstar_pairs.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_vstar_pairs as bvp


def _traj(idx, thinking="думаю", content="ответ", correct=True, done_reason="early_boxed"):
    return {"sample_idx": idx, "thinking": thinking, "content": content,
            "correct": correct, "done_reason": done_reason}


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
```

- [ ] **Step 2: Запустить — verify FAIL**

Run: `cd C:/Work/MITS && uv run pytest tests/test_vstar_pairs.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_vstar_pairs'` (файла ещё нет).

- [ ] **Step 3: Реализовать helpers**

`scripts/build_vstar_pairs.py`:
```python
"""V-STaR within-task pairing (A+B): trajectories -> DPO preference pairs.

A — correctness-mixed (0<n_correct<4); B — completeness в all-correct (4/4).
Без PRM (composite-этап добавит prm/pedagogy scores позже).

Usage: uv run python scripts/build_vstar_pairs.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
TRAJ = ROOT / "training/data/vstar_trajectories_hard.jsonl"
OUT = ROOT / "training/data/vstar_dpo_pairs.jsonl"


def make_completion(traj: dict) -> str:
    """Полный completion: <think>{thinking}</think>\\n{content}."""
    thinking = traj.get("thinking", "").strip()
    content = traj.get("content", "").strip()
    return f"<think>{thinking}</think>\n{content}"


def has_content(traj: dict) -> bool:
    return len(traj.get("content", "").strip()) > 0


def build_pair_record(row: dict, chosen: dict, rejected: dict, strategy: str) -> dict:
    return {
        "pair_id": f"{row['subset_idx']}__{chosen['sample_idx']}__{rejected['sample_idx']}",
        "prompt": [{"role": "user", "content": row["prompt"]}],
        "chosen": make_completion(chosen),
        "rejected": make_completion(rejected),
        "domain": row.get("domain", "?"),
        "difficulty": row.get("difficulty", "hard"),
        "strategy": strategy,
        "scores_chosen": {"correctness": float(chosen["correct"]), "completeness": float(has_content(chosen))},
        "scores_rejected": {"correctness": float(rejected["correct"]), "completeness": float(has_content(rejected))},
    }
```

- [ ] **Step 4: Запустить — verify PASS**

Run: `cd C:/Work/MITS && uv run pytest tests/test_vstar_pairs.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_vstar_pairs.py tests/test_vstar_pairs.py
git commit -m "feat(019): vstar pairing — helpers (completion/record) + tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: select_pair_A (correctness-mixed)

**Files:**
- Modify: `scripts/build_vstar_pairs.py`, `tests/test_vstar_pairs.py`

- [ ] **Step 1: Дописать failing-тесты**

Добавить в `tests/test_vstar_pairs.py`:
```python
def test_select_pair_A_prefers_early_boxed_content_chosen():
    # correct: один early_boxed+content (idx0), один length без content (idx1)
    # incorrect: один с content (idx2), один без (idx3)
    row = {"trajectories": [
        _traj(0, content="реш", correct=True, done_reason="early_boxed"),
        _traj(1, content="", correct=True, done_reason="length"),
        _traj(2, content="невер", correct=False, done_reason="early_boxed"),
        _traj(3, content="", correct=False, done_reason="length"),
    ]}
    ch, rj = bvp.select_pair_A(row)
    assert ch["sample_idx"] == 0  # correct + content + early_boxed
    assert rj["correct"] is False and bvp.has_content(rj)  # incorrect с content
    assert rj["sample_idx"] == 2


def test_select_pair_A_rejected_falls_back_to_truncated():
    # все incorrect без content -> rejected = incorrect (обрезанный)
    row = {"trajectories": [
        _traj(0, content="реш", correct=True),
        _traj(1, content="", correct=False, done_reason="length"),
    ]}
    ch, rj = bvp.select_pair_A(row)
    assert ch["correct"] is True
    assert rj["correct"] is False
```

- [ ] **Step 2: Запустить — verify FAIL**

Run: `cd C:/Work/MITS && uv run pytest tests/test_vstar_pairs.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'select_pair_A'`.

- [ ] **Step 3: Реализовать select_pair_A**

Добавить в `scripts/build_vstar_pairs.py` (перед I/O частью):
```python
def _chosen_key(t: dict) -> tuple:
    # сортировка по приоритету: есть content -> early_boxed -> меньший sample_idx
    return (not has_content(t), t.get("done_reason") != "early_boxed", t["sample_idx"])


def _rejected_key(t: dict) -> tuple:
    # приоритет: есть content (честный контраст) -> меньший sample_idx
    return (not has_content(t), t["sample_idx"])


def select_pair_A(row: dict) -> tuple[dict, dict]:
    """correctness-mixed: chosen=лучшая correct, rejected=лучшая incorrect."""
    trs = row["trajectories"]
    correct = [t for t in trs if t["correct"]]
    incorrect = [t for t in trs if not t["correct"]]
    chosen = min(correct, key=_chosen_key)
    rejected = min(incorrect, key=_rejected_key)
    return chosen, rejected
```

- [ ] **Step 4: Запустить — verify PASS**

Run: `cd C:/Work/MITS && uv run pytest tests/test_vstar_pairs.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_vstar_pairs.py tests/test_vstar_pairs.py
git commit -m "feat(019): vstar pairing — select_pair_A (correctness-mixed) + tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: select_pair_B (completeness в 4/4)

**Files:**
- Modify: `scripts/build_vstar_pairs.py`, `tests/test_vstar_pairs.py`

- [ ] **Step 1: Дописать failing-тесты**

Добавить в `tests/test_vstar_pairs.py`:
```python
def test_select_pair_B_content_vs_truncated():
    # все correct (4/4), смесь: 2 с content, 2 обрезаны
    row = {"trajectories": [
        _traj(0, content="полный1", correct=True, done_reason="early_boxed"),
        _traj(1, content="", correct=True, done_reason="length"),
        _traj(2, content="полный2", correct=True, done_reason="early_boxed"),
        _traj(3, content="", correct=True, done_reason="length"),
    ]}
    res = bvp.select_pair_B(row)
    assert res is not None
    ch, rj = res
    assert bvp.has_content(ch) and not bvp.has_content(rj)
    assert ch["sample_idx"] == 0 and rj["sample_idx"] == 1


def test_select_pair_B_none_when_all_content():
    # все correct + все с content -> нет completeness-контраста
    row = {"trajectories": [_traj(i, content="x", correct=True) for i in range(4)]}
    assert bvp.select_pair_B(row) is None
```

- [ ] **Step 2: Запустить — verify FAIL**

Run: `cd C:/Work/MITS && uv run pytest tests/test_vstar_pairs.py -q`
Expected: FAIL — нет атрибута `select_pair_B`.

- [ ] **Step 3: Реализовать select_pair_B**

Добавить в `scripts/build_vstar_pairs.py`:
```python
def select_pair_B(row: dict) -> tuple[dict, dict] | None:
    """completeness в 4/4: chosen=correct+content, rejected=correct+обрезка. None если нет смеси."""
    trs = row["trajectories"]
    with_c = [t for t in trs if has_content(t)]
    without_c = [t for t in trs if not has_content(t)]
    if not with_c or not without_c:
        return None
    chosen = min(with_c, key=lambda t: t["sample_idx"])
    rejected = min(without_c, key=lambda t: t["sample_idx"])
    return chosen, rejected
```

- [ ] **Step 4: Запустить — verify PASS**

Run: `cd C:/Work/MITS && uv run pytest tests/test_vstar_pairs.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_vstar_pairs.py tests/test_vstar_pairs.py
git commit -m "feat(019): vstar pairing — select_pair_B (completeness) + tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: build_all_pairs + main + run на реальных данных + verify

**Files:**
- Modify: `scripts/build_vstar_pairs.py`, `tests/test_vstar_pairs.py`

- [ ] **Step 1: Дописать тест build_all_pairs (синтетика 3 строки)**

Добавить в `tests/test_vstar_pairs.py`:
```python
def test_build_all_pairs_strategies():
    rows = [
        # mixed -> A
        {"subset_idx": 0, "prompt": "p0", "domain": "math", "difficulty": "hard", "n_correct": 2,
         "trajectories": [_traj(0, content="c", correct=True), _traj(1, content="", correct=False, done_reason="length"),
                          _traj(2, content="c", correct=True), _traj(3, content="w", correct=False)]},
        # 4/4 смесь -> B
        {"subset_idx": 1, "prompt": "p1", "domain": "cs", "difficulty": "hard", "n_correct": 4,
         "trajectories": [_traj(0, content="c", correct=True), _traj(1, content="", correct=True, done_reason="length"),
                          _traj(2, content="c", correct=True), _traj(3, content="c", correct=True)]},
        # 0/4 -> пропуск
        {"subset_idx": 2, "prompt": "p2", "domain": "bio", "difficulty": "hard", "n_correct": 0,
         "trajectories": [_traj(i, content="", correct=False) for i in range(4)]},
    ]
    pairs = bvp.build_all_pairs(rows)
    strat = sorted(p["strategy"] for p in pairs)
    assert strat == ["A", "B"]  # 0/4 пропущен
    assert all(p["chosen"] for p in pairs)
    assert len({p["pair_id"] for p in pairs}) == 2
```

- [ ] **Step 2: Запустить — verify FAIL**

Run: `cd C:/Work/MITS && uv run pytest tests/test_vstar_pairs.py -q`
Expected: FAIL — нет `build_all_pairs`.

- [ ] **Step 3: Реализовать build_all_pairs + main**

Добавить в `scripts/build_vstar_pairs.py`:
```python
def build_all_pairs(rows: list[dict]) -> list[dict]:
    pairs = []
    for row in rows:
        nc = row["n_correct"]
        if 0 < nc < 4:
            ch, rj = select_pair_A(row)
            pairs.append(build_pair_record(row, ch, rj, "A"))
        elif nc == 4:
            res = select_pair_B(row)
            if res is not None:
                ch, rj = res
                pairs.append(build_pair_record(row, ch, rj, "B"))
    return pairs


def main() -> None:
    rows = [json.loads(line) for line in TRAJ.open(encoding="utf-8") if line.strip()]
    pairs = build_all_pairs(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    from collections import Counter
    strat = Counter(p["strategy"] for p in pairs)
    dom = Counter(p["domain"] for p in pairs)
    print(f"[ok] {len(pairs)} пар -> {OUT}")
    print(f"  strategy: {dict(strat)}")
    print(f"  domain: {dict(dom)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Запустить тесты — verify PASS**

Run: `cd C:/Work/MITS && uv run pytest tests/test_vstar_pairs.py -q`
Expected: 9 passed.

- [ ] **Step 5: Запустить на реальных данных**

Run: `cd C:/Work/MITS && uv run python scripts/build_vstar_pairs.py`
Expected: `[ok] 84 пар -> ...vstar_dpo_pairs.jsonl`, strategy `{'A': 65, 'B': 19}`, domain breakdown (math доминирует).

- [ ] **Step 6: Verify итогового датасета**

Run:
```bash
cd C:/Work/MITS && uv run python -c "
import json
P=[json.loads(l) for l in open('training/data/vstar_dpo_pairs.jsonl',encoding='utf-8') if l.strip()]
print('пар:', len(P))
print('пустой chosen:', sum(1 for p in P if not p['chosen'].strip()))
print('уникальных pair_id:', len({p['pair_id'] for p in P}))
print('chosen==rejected:', sum(1 for p in P if p['chosen']==p['rejected']))
from collections import Counter
print('strategy:', dict(Counter(p['strategy'] for p in P)))
print('domain:', dict(Counter(p['domain'] for p in P)))
print('prompt conversational:', all(isinstance(p['prompt'],list) and p['prompt'][0]['role']=='user' for p in P))
"
```
Expected: пар≈84, пустой chosen=0, уникальных pair_id=len(P), chosen==rejected=0, strategy {A:65,B:19}, prompt conversational True.

- [ ] **Step 7: Commit (скрипт + тесты + датасет)**

```bash
git add scripts/build_vstar_pairs.py tests/test_vstar_pairs.py training/data/vstar_dpo_pairs.jsonl
git commit -m "feat(019): vstar pairing — build_all_pairs + 84 DPO pairs dataset

A=65 (correctness-mixed) + B=19 (completeness). Все тесты PASS,
0 пустых chosen, уникальные pair_id, chosen!=rejected.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (выполнено при написании плана)

**1. Spec coverage:**
- build_vstar_pairs.py + dpo_pairs.jsonl → Tasks 1-4 ✓
- Within-task (1 пара/problem) → build_all_pairs (один append на row) ✓
- Стратегия A → Task 2; B → Task 3 ✓
- Формат (pair_id/prompt/chosen/rejected/scores) → Task 1 build_pair_record ✓
- completion scope thinking+content → make_completion (Task 1) ✓
- Verification (84, нет пустых, уникальные, chosen≠rejected, A/B split) → Task 4 Step 6 ✓
- YAGNI (без PRM, без B2, 1 пара/problem) → build_all_pairs пропускает nc==0 ✓

**2. Placeholder scan:** код полный, тесты с реальными assert. Нет TBD/заглушек.

**3. Type consistency:** `make_completion(traj)->str`, `has_content(traj)->bool`, `select_pair_A(row)->tuple`, `select_pair_B(row)->tuple|None`, `build_pair_record(row,chosen,rejected,strategy)->dict`, `build_all_pairs(rows)->list[dict]`. Имена и сигнатуры консистентны между тестами (Task 1-4) и реализацией. `_chosen_key`/`_rejected_key` приватные, используются только в select_pair_A. Тестовый helper `_traj()` единый во всех тестах.
