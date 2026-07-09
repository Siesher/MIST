# Mastery Surfacing (track D1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface real per-student BKT mastery — `p(known)` per topic — on the Knowledge Forge graph (node rings) and inside the dreaming reflection, computed on-read from already-stored interactions.

**Architecture:** Derive-on-read. A pure `MasteryService` builds an ephemeral in-memory `StudentModel` (`src/models/knowledge_tracing.py`) and replays the student's stored graded outcomes (`MessageTable.is_correct`, with a session-level fallback) through the existing BKT update — no writes, no second DB, no streaming-path change. The backend returns topic-keyed mastery; the **frontend** maps topic→graph-node by the node-id slug (`<domain>:<slug>:<type>`) and renders real rings or an honest "no data" state.

**Tech Stack:** Python 3.11 (FastAPI, SQLAlchemy async, existing BKT engine), Next.js 14 / TypeScript / SVG graph.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `backend/app/services/session_signals.py` | Create | Shared `parse_task_json` / `resolve_topic` / `normalize_topic` (one source of topic logic for dreaming + mastery) |
| `tests/test_session_signals.py` | Create | Unit tests for the helpers |
| `backend/app/services/dreaming_service.py` | Modify | Use `session_signals` (drop local `_parse_task`); pass mastery into reflection |
| `backend/app/services/mastery_service.py` | Create | `compute_mastery(rows) -> list[MasterySignal]` (BKT replay) + `mastery_by_skill` |
| `tests/test_mastery_service.py` | Create | Replay, fallback, empty, mapping tests |
| `backend/app/api/v1/students.py` | Modify | `GET /students/me/mastery`; rewire `/me/knowledge` to real data |
| `tests/test_mastery_endpoint.py` | Create | Anonymous endpoint test |
| `src/agents/reflection.py` | Modify | Accept `mastery=` and render a "Текущее мастерство (BKT)" prompt block |
| `tests/test_reflection.py` | Modify | Assert the mastery block reaches the prompt |
| `frontend/src/lib/api.ts` | Modify | `getMastery()` + types |
| `frontend/src/app/graph/graphData.ts` | Modify | Fetch mastery; real `m` + `hasMastery` via slug; drop `synthMastery` |
| `frontend/src/app/graph/page.tsx` | Modify | Honor `hasMastery` ("no data"); real BKT; DKT="preview — D2" |

---

## Task 1: Shared session-signal helpers

**Files:**
- Create: `backend/app/services/session_signals.py`
- Test: `tests/test_session_signals.py`
- Modify: `backend/app/services/dreaming_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_session_signals.py
from backend.app.services.session_signals import (
    parse_task_json,
    resolve_topic,
    normalize_topic,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_session_signals.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.services.session_signals'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/session_signals.py
"""Shared helpers to read learning signals from stored session rows.

Used by both the dreaming reflection digest and the mastery service so topic
resolution stays identical across them (no drift).
"""

from __future__ import annotations

import json
from typing import Any


def parse_task_json(task_json: Any) -> dict:
    """Parse a session's ``task_json`` column into a dict (best-effort)."""
    if not task_json:
        return {}
    if isinstance(task_json, dict):
        return task_json
    try:
        data = json.loads(task_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_topic(row: Any) -> str:
    """Best topic label: explicit ``topic`` → task ``topic`` → ``subject`` → ``"general"``."""
    task = parse_task_json(getattr(row, "task_json", None))
    topic = getattr(row, "topic", None) or task.get("topic") or task.get("subject") or "general"
    return str(topic)


def normalize_topic(topic: str) -> str:
    """Canonical key for matching a topic against graph node-id slugs."""
    return topic.strip().lower().replace(" ", "_").replace("-", "_")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_session_signals.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Refactor `dreaming_service._digest_from_rows` to use the shared helper**

In `backend/app/services/dreaming_service.py`: delete the local `_parse_task` function and import the shared helpers. Replace the import block and the two usages.

Change the imports near the top (after `from typing import Any, List`):

```python
from backend.app.services.session_signals import parse_task_json, resolve_topic
from src.agents.reflection import ReflectionGenerator, SessionDigest
from src.memory.memory_files import StudentMemoryFiles
```

Delete the entire local `def _parse_task(...)` function.

In `_digest_from_rows`, replace the two lines that used the local helper:

```python
        task = parse_task_json(getattr(r, "task_json", None))
        subject = str(task.get("subject") or "")
        topic = resolve_topic(r)
```

(Leaves the rest of `_digest_from_rows` — `answer`, `difficulty`, transcript, etc. — unchanged.)

- [ ] **Step 6: Run to verify the refactor is green**

Run: `uv run pytest tests/test_session_signals.py tests/test_dreaming_service.py tests/test_reflection.py -q`
Expected: PASS (all previously-passing dreaming tests still pass)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/session_signals.py tests/test_session_signals.py backend/app/services/dreaming_service.py
git commit -m "refactor(dreaming): extract shared session_signals (parse_task/resolve_topic)"
```

---

## Task 2: MasteryService (BKT replay-on-read)

**Files:**
- Create: `backend/app/services/mastery_service.py`
- Test: `tests/test_mastery_service.py`

- [ ] **Step 1: Write the failing test**

```python
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
    mixed = compute_mastery([_Row("t", [_Msg(is_correct=True), _Msg(is_correct=False), _Msg(is_correct=True)])])[0].p_known
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mastery_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.services.mastery_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/mastery_service.py
"""Derive per-student mastery on-read by replaying stored interactions through BKT.

Reuses the existing BKT engine (``src/models/knowledge_tracing.StudentModel``): an
ephemeral in-memory model is fed the student's graded outcomes in time order and the
resulting per-skill ``mastery`` (= p(known)) is read back. No persistence, no DKT
model attached (so ``update_skill`` is pure BKT), no change to the live session path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

from backend.app.services.session_signals import resolve_topic
from src.models.knowledge_tracing import StudentModel


@dataclass
class MasterySignal:
    """Per-topic mastery distilled from a student's interaction history."""

    topic: str
    p_known: float
    attempts: int
    correct: int
    last_seen: Optional[str] = None  # ISO-8601, or None


def _outcomes(rows: List[Any]) -> tuple[list[tuple[datetime, str, bool]], dict[str, datetime]]:
    """Return chronological (timestamp, topic, is_correct) outcomes and per-topic last_seen.

    Primary signal: messages carrying a non-null ``is_correct`` (one BKT update each).
    Fallback (no graded messages in a session): a single session-level outcome —
    solved → correct; attempted-but-unsolved → incorrect; otherwise skipped.
    """
    outcomes: list[tuple[datetime, str, bool]] = []
    last_seen: dict[str, datetime] = {}
    for r in rows:
        topic = resolve_topic(r)
        msgs = list(getattr(r, "messages", []) or [])
        graded = [m for m in msgs if getattr(m, "is_correct", None) is not None]
        if graded:
            for m in graded:
                ts = getattr(m, "timestamp", None) or datetime.min
                outcomes.append((ts, topic, bool(m.is_correct)))
        else:
            ts = getattr(r, "updated_at", None) or getattr(r, "created_at", None) or datetime.min
            if getattr(r, "is_solved", False):
                outcomes.append((ts, topic, True))
            elif int(getattr(r, "attempts", 0) or 0) > 0:
                outcomes.append((ts, topic, False))
        rts = getattr(r, "updated_at", None) or getattr(r, "created_at", None)
        if rts and (topic not in last_seen or rts > last_seen[topic]):
            last_seen[topic] = rts
    return outcomes, last_seen


def compute_mastery(rows: List[Any]) -> List[MasterySignal]:
    """Compute per-topic BKT mastery for a student's recent session rows.

    Args:
        rows: Session rows exposing ``topic`` / ``task_json``, a ``messages``
            collection (with ``is_correct`` / ``timestamp``), and
            ``is_solved`` / ``attempts`` / ``created_at`` / ``updated_at``.

    Returns:
        One :class:`MasterySignal` per practiced topic, weakest first.
    """
    outcomes, last_seen = _outcomes(rows)
    outcomes.sort(key=lambda o: o[0])
    model = StudentModel(student_id="ephemeral")
    for _ts, topic, is_correct in outcomes:
        model.update_skill(topic, is_correct)

    signals = [
        MasterySignal(
            topic=name,
            p_known=round(skill.mastery, 4),
            attempts=skill.attempts,
            correct=skill.successes,
            last_seen=last_seen[name].isoformat() if name in last_seen else None,
        )
        for name, skill in model.skills.items()
    ]
    signals.sort(key=lambda s: s.p_known)  # weakest first
    return signals


def mastery_by_skill(signals: List[MasterySignal]) -> dict:
    """Flatten signals to a ``{topic: p_known}`` dict for clients."""
    return {s.topic: s.p_known for s in signals}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mastery_service.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/mastery_service.py tests/test_mastery_service.py
git commit -m "feat(mastery): MasteryService — BKT replay-on-read from stored interactions"
```

---

## Task 3: Mastery endpoint + rewire knowledge state

**Files:**
- Modify: `backend/app/api/v1/students.py`
- Test: `tests/test_mastery_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mastery_endpoint.py
from fastapi.testclient import TestClient

from backend.app.main import app


def test_mastery_endpoint_anonymous():
    client = TestClient(app)
    r = client.get("/api/v1/students/me/mastery")
    assert r.status_code == 200
    body = r.json()
    assert "topics" in body
    assert "mastery_by_skill" in body
    assert isinstance(body["topics"], list)
    assert isinstance(body["mastery_by_skill"], dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mastery_endpoint.py -q`
Expected: FAIL — 404 (route not registered)

- [ ] **Step 3: Add the endpoint + rewire knowledge state**

In `backend/app/api/v1/students.py`, extend the imports at the top:

```python
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime

from backend.app.api.v1.auth import get_optional_user
from backend.app.models.database import get_db
from backend.app.models.tables import SessionTable, UserTable
from backend.app.services.mastery_service import compute_mastery, mastery_by_skill
from backend.app.schemas.chat import (
    StudentProfileResponse,
    AnalyticsResponse,
    KnowledgeStateResponse,
    ProgressByDay,
)
from backend.app.services.orchestrator_service import get_orchestrator_service
```

Add a private helper to load recent rows (mirrors the `/dream` query):

```python
async def _recent_rows(db: AsyncSession, user: UserTable | None, limit: int = 50):
    q = (
        select(SessionTable)
        .options(selectinload(SessionTable.messages))
        .where(SessionTable.user_id == (user.id if user else None))
        .order_by(SessionTable.updated_at.desc())
        .limit(limit)
    )
    return (await db.execute(q)).scalars().all()
```

Add the new endpoint:

```python
@router.get("/me/mastery")
async def get_mastery(
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
) -> dict:
    """Real per-topic BKT mastery for the current (or anonymous) student."""
    rows = await _recent_rows(db, user)
    signals = compute_mastery(rows)
    return {
        "topics": [asdict(s) for s in signals],
        "mastery_by_skill": mastery_by_skill(signals),
    }
```

Rewire the existing `/me/knowledge` endpoint to serve real data instead of the orchestrator stub. Replace the whole `get_knowledge_state` route function with:

```python
@router.get("/me/knowledge", response_model=KnowledgeStateResponse)
async def get_knowledge_state(
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
):
    """Get current knowledge state (real BKT mastery; weakest topics as next focus)."""
    rows = await _recent_rows(db, user)
    signals = compute_mastery(rows)
    return KnowledgeStateResponse(
        mastery_by_skill=mastery_by_skill(signals),
        skill_dependencies={},
        recommended_next=[s.topic for s in signals[:3]],  # weakest first
    )
```

(The hardcoded `orchestrator_service.get_knowledge_state` stub is now unused by this route; leave it in place — removing it is out of scope.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mastery_endpoint.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Verify nothing else broke**

Run: `uv run python -m py_compile backend/app/api/v1/students.py`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/students.py tests/test_mastery_endpoint.py
git commit -m "feat(mastery): GET /students/me/mastery + real /me/knowledge"
```

---

## Task 4: Feed mastery into the dreaming reflection

**Files:**
- Modify: `src/agents/reflection.py`
- Modify: `backend/app/services/dreaming_service.py`
- Test: `tests/test_reflection.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_reflection.py` (the existing `_FakeLLM` records nothing; add a prompt-capturing fake at the end of the file):

```python
def test_reflection_includes_mastery_block():
    """When mastery is supplied, it is rendered into the prompt the LLM receives."""
    import json as _json

    captured = {}

    class _CapturingLLM:
        def generate(self, prompt, system=None, **kw):
            captured["prompt"] = prompt
            return _json.dumps({"reflection_md": "ok", "profile_md": "p"})

    from src.memory.memory_files import StudentMemoryFiles

    def _mk(tmp):
        return StudentMemoryFiles("masterystud", base_dir=tmp)

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        mem = _mk(tmp)
        gen = ReflectionGenerator(llm=_CapturingLLM(), memory=mem)
        gen.reflect(_digest(), mastery=[{"topic": "derivatives", "p_known": 0.42, "attempts": 7}])
    assert "Текущее мастерство" in captured["prompt"]
    assert "derivatives" in captured["prompt"]
    assert "0.42" in captured["prompt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reflection.py::test_reflection_includes_mastery_block -q`
Expected: FAIL — `reflect()` got an unexpected keyword argument `mastery` (or the assertion fails).

- [ ] **Step 3: Add the `mastery` parameter + prompt block**

In `src/agents/reflection.py`, change `reflect` to accept mastery and thread it into the prompt:

```python
    def reflect(self, digests: List[SessionDigest], *, mastery: list | None = None) -> ReflectionResult:
```

(keep the existing docstring; add an Args line for `mastery`: "Optional list of `{topic, p_known, attempts}` dicts to ground the analysis in the BKT estimate.")

Inside `reflect`, change the prompt build call:

```python
        prompt = self._build_prompt(digests, mastery)
```

Update `_build_prompt`'s signature and append the block before the profile section:

```python
    def _build_prompt(self, digests: List[SessionDigest], mastery: list | None = None) -> str:
```

After the loop that builds `blocks` and before reading the profile (`prof = self._mem.read_profile()`), insert:

```python
        prompt = "Недавние занятия ученика (разбери их подробно):\n\n" + "\n\n".join(blocks)
        if mastery:
            lines = ["Текущее мастерство (BKT) — p(known) по темам:"]
            for m in mastery[:12]:
                topic = m.get("topic", "?")
                pk = m.get("p_known", 0.0)
                n = m.get("attempts", 0)
                lines.append(f"- {topic}: p(known)={pk:.2f} (попыток {n})")
            prompt += "\n\n" + "\n".join(lines)
```

Then keep the existing profile-append and `return prompt`. (Remove the now-duplicate `prompt = "Недавние занятия..."` assignment that previously started the return section — there must be exactly one.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reflection.py -q`
Expected: PASS (all reflection tests, including the new one)

- [ ] **Step 5: Wire DreamingService to compute + pass mastery**

In `backend/app/services/dreaming_service.py`, import the mastery service near the other imports:

```python
from backend.app.services.mastery_service import compute_mastery
```

In `dream_from_rows`, compute mastery from the same rows and pass it to `reflect`. Replace the `result = gen.reflect(digests)` line with:

```python
        mastery = [
            {"topic": s.topic, "p_known": s.p_known, "attempts": s.attempts}
            for s in compute_mastery(rows)
        ]
        result = gen.reflect(digests, mastery=mastery)
```

- [ ] **Step 6: Verify**

Run: `uv run pytest tests/test_reflection.py tests/test_dreaming_service.py -q`
Expected: PASS (the dreaming tests still pass — `_FakeLLM`/`_ok_llm` ignore the extra prompt content; `compute_mastery` runs over the stub rows).

- [ ] **Step 7: Commit**

```bash
git add src/agents/reflection.py backend/app/services/dreaming_service.py tests/test_reflection.py
git commit -m "feat(mastery): dreaming reflection grounded in BKT mastery"
```

---

## Task 5: Frontend — mastery client + real graph mastery

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/graph/graphData.ts`

- [ ] **Step 1: Capture green tsc baseline**

Run (in `frontend/`): `npx tsc --noEmit`
Expected: exit 0 (so any new error is attributable to this task).

- [ ] **Step 2: Add the mastery client fn + types in `api.ts`**

Add near the other client fns (after the Dreaming block):

```typescript
// --- Mastery (per-student BKT) ---

export interface MasterySignal {
  topic: string;
  p_known: number;
  attempts: number;
  correct: number;
  last_seen: string | null;
}
export async function getMastery(): Promise<{
  topics: MasterySignal[];
  mastery_by_skill: Record<string, number>;
}> {
  return request("/students/me/mastery");
}
```

- [ ] **Step 3: Use real mastery in `graphData.ts`**

Add `hasMastery` to the node types. In `interface GraphNode` add after `att`:

```typescript
  /** Whether `m` is real per-student mastery (vs unpractised "no data"). */
  hasMastery?: boolean;
```

In the `RawNode` type add `hasMastery: boolean;`.

In `layoutNodes`, carry the flag through to the output object (add `hasMastery: n.hasMastery` to the pushed `out.push({...})`), and make the radius not inflate for no-data nodes:

```typescript
      const r = Math.round(18 + (n.hasMastery ? n.m * 6 : 0) + Math.min(1, n.att / 120) * 4);
```

Add a slug normalizer near the other helpers:

```typescript
/** Concept slug of a node id `<domain>:<slug>:<type>`, normalized for topic matching. */
function nodeSlug(id: string): string {
  const seg = id.split(":")[1] ?? "";
  return seg.trim().toLowerCase().replace(/[\s-]+/g, "_");
}
```

Import `getMastery` from `@/lib/api` (add to the existing import list).

In `fetchGraph`, fetch mastery alongside the summaries and build a normalized map:

```typescript
  const [summaries, mastery] = await Promise.all([
    listKnowledgeNodes({ limit: maxNodes }),
    getMastery().catch(() => ({ mastery_by_skill: {} as Record<string, number> })),
  ]);
  const masteryMap: Record<string, number> = {};
  for (const [topic, pk] of Object.entries(mastery.mastery_by_skill ?? {})) {
    masteryMap[topic.trim().toLowerCase().replace(/[\s-]+/g, "_")] = pk;
  }
```

(Remove the old `const [summaries] = await Promise.all([... getGraphStats() ...])` line; if `getGraphStats` was only used there for `.catch`, drop it — it was discarded anyway.)

Replace the `baseNodes` construction to use real mastery instead of `synthMastery`/`synthAttempts`:

```typescript
  const baseNodes = summaries.map((s: KnowledgeNodeSummary) => {
    const d = mapDomain(s.domain);
    const slug = nodeSlug(s.id);
    const real = masteryMap[slug];
    const hasMastery = real !== undefined;
    const m = hasMastery ? real : 0;
    const labEn = s.title_en?.trim() || s.title?.trim() || s.id;
    return {
      id: s.id,
      lab: labEn,
      labRu: s.title?.trim() || labEn,
      d,
      m,
      att: 0,
      difficulty: s.difficulty ?? 0.5,
      hasMastery,
    };
  });
```

Delete the now-unused `synthMastery` and `synthAttempts` functions.

In step 4 of `fetchGraph` (active/weak marking), only consider real-mastery nodes for the "weakest" highlight:

```typescript
    const practised = nodes.filter((n) => n.hasMastery);
    const active = [...nodes].sort((a, b) => b.att - a.att)[0];
    const weak = [...practised].sort((a, b) => a.m - b.m)[0];
    if (active) active.active = true;
    if (weak && weak.id !== active?.id) weak.highlight = true;
```

(Leave the FALLBACK_NODES literals as-is — the static fallback keeps its demo mastery; `hasMastery` is `undefined` there, which the page treats as real for the curated demo. To keep the fallback showing rings, set `hasMastery: true` on each FALLBACK node — add `hasMastery: true,` to each literal, OR simpler: in the page, treat `hasMastery !== false` as "has data". Use the page-side rule in Task 6 so no fallback edits are needed.)

- [ ] **Step 4: Verify tsc**

Run (in `frontend/`): `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/app/graph/graphData.ts
git commit -m "feat(mastery): graph fetches real per-student BKT mastery"
```

---

## Task 6: Frontend — honest rendering (no-data + real BKT + DKT preview)

**Files:**
- Modify: `frontend/src/app/graph/page.tsx`

The rule: a node "has data" when `n.hasMastery !== false` (so curated FALLBACK nodes, where it is `undefined`, still render rings; only real backend nodes explicitly set `false`).

- [ ] **Step 1: Capture green tsc baseline**

Run (in `frontend/`): `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 2: Add an i18n key for the DKT preview + no-data**

In both `ru` and `en` blocks of `GRAPH_I18N`, add:

```typescript
    graphNoData: lang === "ru" ? "нет данных" : "no data",  // (write the literal per block)
    graphSoon: "D2",
```

Concretely, in the `ru` block add `graphNoData: "нет данных",` and `graphSoon: "D2",`; in the `en` block add `graphNoData: "no data",` and `graphSoon: "D2",`.

- [ ] **Step 3: Node badge — real BKT, DKT preview, no-data**

Find the node badge (around line 578):

```tsx
                          {metric === "bkt"
                            ? (n.m * 0.95).toFixed(2)
                            : metric === "dkt"
                              ? ((n.m - 0.5) * 4).toFixed(2)
                              : Math.round(n.m * 100)}
```

Replace with:

```tsx
                          {n.hasMastery === false
                            ? "—"
                            : metric === "bkt"
                              ? n.m.toFixed(2)
                              : metric === "dkt"
                                ? tt("graphSoon")
                                : Math.round(n.m * 100)}
```

- [ ] **Step 4: Mastery ring — muted for no-data**

Find the ring (around line 552):

```tsx
                          strokeDasharray={`${(n.m * 2 * Math.PI * (n.r + 4)).toFixed(1)} 9999`}
```

For no-data nodes the arc length is 0 (no progress shown). Replace with:

```tsx
                          strokeDasharray={`${(n.hasMastery === false ? 0 : n.m * 2 * Math.PI * (n.r + 4)).toFixed(1)} 9999`}
```

- [ ] **Step 5: Inspect panel — real BKT + DKT preview + no-data**

Find the inspect panel metrics (around lines 668-686). Replace the mastery percentage, bar, BKT, DKT lines so they honor `hasMastery`:

```tsx
                        {Math.round((sel.hasMastery === false ? 0 : sel.m) * 100)}%
```

bar fill:

```tsx
                      <div className="gs-bar-fill" style={{ width: (sel.hasMastery === false ? 0 : sel.m) * 100 + "%" }} />
```

BKT value:

```tsx
                        <div className="v">{sel.hasMastery === false ? tt("graphNoData") : sel.m.toFixed(2)}</div>
```

DKT value:

```tsx
                        <div className="v">{tt("graphSoon")}</div>
```

- [ ] **Step 6: Verify tsc**

Run (in `frontend/`): `npx tsc --noEmit`
Expected: exit 0. Live check: open `/graph`; nodes for practiced topics show real p(known), unpracticed show "—"/"no data", the DKT toggle shows "D2".

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/graph/page.tsx
git commit -m "feat(mastery): graph shows real BKT, honest no-data, DKT preview"
```

---

## Self-Review

**Spec coverage:** §Architecture (derive-on-read, ephemeral StudentModel) → Task 2. §Data flow + signal robustness (per-message `is_correct` + session fallback) → Task 2 `_outcomes`. §topic↔node mapping (slug) → Task 5 `nodeSlug`/`masteryMap` (frontend, planning refinement of the spec's `by_node`; backend stays topic-keyed). §Endpoints (`/me/mastery` + rewire `get_knowledge_state`) → Task 3. §Graph wiring (real rings, "no data") → Tasks 5-6. §Dreaming integration → Task 4. §Shared topic helper (open item #2) → Task 1. §Testing → Tasks 1-4 unit + endpoint; 5-6 tsc. §Deferred (DKT/decay/affect) → DKT honestly labeled "D2", not implemented.

**Placeholder scan:** every code step contains full code; the only "TODO-like" item (FALLBACK `hasMastery`) is resolved by the page-side `!== false` rule (Task 6 header), so no FALLBACK edits are needed.

**Type consistency:** `MasterySignal` fields (`topic/p_known/attempts/correct/last_seen`) are identical in Task 2 (dataclass), Task 3 (`asdict`), and Task 5 (TS interface). `compute_mastery(rows)` / `mastery_by_skill(signals)` names match across Tasks 2-4. `reflect(digests, *, mastery=...)` signature matches the Task 4 call in `dream_from_rows`. `resolve_topic`/`parse_task_json` names match across Tasks 1-2. Frontend `getMastery()` return shape matches the Task 3 endpoint body.

**Open items (from spec) resolved:** (1) `is_correct` is populated live (verified: `orchestrator_service.py:820-823,1599`), so the per-message path is primary; fallback covers the rest. (2) shared helper = Task 1 `session_signals`. (3) `get_knowledge_state` rewired at the endpoint (Task 3), orchestrator stub left untouched.
