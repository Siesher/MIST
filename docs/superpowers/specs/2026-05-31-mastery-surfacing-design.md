# D1 — Real per-student mastery on the graph + in dreaming (surfacing)

**Status:** Design approved 2026-05-31. First sub-project of "track D" (auxiliary-model work).
The second sub-project — **model quality / SOTA** (DKT training, attention-based KT, affect/cognitive-load upgrades) — gets its own spec later.

## Goal

Surface **real per-student knowledge mastery** (BKT `p(known)` per topic) in two places that
currently show nothing real:

1. the Knowledge Forge **graph** (node mastery rings), and
2. the **dreaming** reflection (ground the "сон" analysis in actual mastery numbers).

…without touching the live streaming path and without standing up a second database.

## Background (verified findings)

- `backend/app/services/orchestrator_service.py:1804` `get_knowledge_state()` returns a **hardcoded
  stub** (`mastery_by_skill: {}`, `recommended_next: ["derivatives","limits"]`). The `/students/me/knowledge`
  endpoint (`backend/app/api/v1/students.py:47`) serves this stub.
- The backend **never imports** `StudentMemory` / `MemoryManager` / `update_knowledge_state` — the BKT/DKT
  engine in `src/` is disconnected from the live FastAPI path. **No real per-student mastery is persisted anywhere.**
- The frontend graph (`frontend/src/app/graph/graphData.ts` `synthMastery()`) fabricates mastery
  deterministically from node `difficulty`+`confidence`. The `mastery / bkt / dkt` toggle
  (`frontend/src/app/graph/page.tsx`) is a label over synthetic data.
- **But** every graded interaction *is* stored by the live backend: `MessageTable` (`role`, `content`,
  `move_type`, `is_correct`) and `SessionTable` (`topic`, `is_solved`, `attempts`, `hints_used`, `task_json`,
  `created_at`/`updated_at`).
- A correct, reusable **BKT engine** exists at `src/models/knowledge_tracing.py`: `StudentModel.update_skill(skill, is_correct)`
  (Bayes update `_bkt_update`, line 342) with `SkillState` params (p_init 0.3, p_learn 0.1, p_forget 0.05,
  p_guess 0.2, p_slip 0.1), plus `get_mastery`, `get_knowledge_state_summary`. With no `dkt_model` set it is pure BKT.
- Graph node ids are `<domain>:<concept_slug>:<type>` (e.g. `math:linear_equations:definition`); the **middle
  slug is a topic key** and session topics use the same vocabulary → deterministic topic↔node mapping.

## Architecture — derive-on-read

A new read-only **`MasteryService`**. On request it builds an **ephemeral in-memory `StudentModel`**
(no persistence), replays the student's stored interactions chronologically via `update_skill(topic, is_correct)`,
and reads back per-topic mastery. Reuses the existing BKT math verbatim; introduces **no** new model, **no**
writes, **no** second DB, and **no** change to the WebSocket/streaming path.

```
sessions+messages (existing app DB)
   → group graded outcomes by topic, ordered by time
   → replay through an in-memory StudentModel (pure BKT)
   → {topic: {p_known, attempts, correct, last_seen}}
   → (a) graph: map topic→nodes by slug → rings
       (b) dreaming: inject as a "current mastery" block in the digest
```

## Components / file structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `backend/app/services/mastery_service.py` | Create | `MasteryService.compute(rows) -> dict[topic, MasterySignal]` (BKT replay) + `topic_to_node_ids` slug mapping helper |
| `tests/test_mastery_service.py` | Create | BKT replay, fallback, slug mapping unit tests |
| `backend/app/api/v1/students.py` | Modify | `GET /students/me/mastery`; rewire `get_knowledge_state` to real data |
| `backend/app/services/orchestrator_service.py` | Modify | replace the `get_knowledge_state` stub to delegate to `MasteryService` (or remove if endpoint queries DB directly — decided in planning) |
| `tests/test_mastery_endpoint.py` | Create | anonymous → 200 with mastery shape |
| `backend/app/services/dreaming_service.py` | Modify | pass per-topic mastery into the digest |
| `src/agents/reflection.py` | Modify | render a "Текущее мастерство (BKT)" block in the prompt |
| `frontend/src/lib/api.ts` | Modify | `getMastery()` client fn + type |
| `frontend/src/app/graph/graphData.ts` | Modify | replace `synthMastery` with real mastery via slug map; "no data" when absent |
| `frontend/src/app/graph/page.tsx` | Modify | rings from real data; `dkt` toggle labeled "preview — трек D2" |

## Data flow detail

**Interaction → outcomes.** Per session, resolve `topic` (`session.topic` → else `task_json.topic` → else slug
from problem; same resolution as the dreaming digest). Collect chronological graded outcomes:
- **Primary signal:** messages with non-null `is_correct` → one BKT update each (`update_skill(topic, is_correct)`).
- **Fallback signal (when `is_correct` is sparse/absent):** one coarse outcome per session — `is_solved == True`
  → correct; `attempts > 0 and not is_solved` → incorrect; otherwise skip. Guarantees real mastery from whatever
  the backend actually records. *(Which signal dominates is verified in planning by inspecting live `is_correct` population.)*

**Replay.** One ephemeral `StudentModel(student_id)`; feed outcomes in time order across all sessions for a topic;
read `get_mastery(topic)` (= `p_known`), plus `attempts`, `successes`, `last_practice`.

**Output unit:** `MasterySignal{ topic, p_known: float, attempts: int, correct: int, last_seen: iso str|None }`.

## topic↔node mapping

`concept_slug(node) = node.id.split(":")[1]`. Normalize both topic and slug (`lower()`, spaces/hyphens→`_`).
A node carries a mastery value iff its slug equals a practiced topic. Topics with no matching node → returned in a
`topics` list for a side panel; nodes with no matching topic → **`mastery: null`** ("no data", neutral render —
never synthetic).

## Endpoints

- `GET /students/me/mastery` → `{ topics: [MasterySignal...], by_node: { "<node_id>": p_known } }`.
  Anonymous caller → `student_default` (sessions with `user_id IS NULL`), consistent with `/dream`.
- `get_knowledge_state` stub rewired to return real `mastery_by_skill` from `MasteryService`
  (`recommended_next` from weakest practiced skills via the engine's `get_weakest_skills`).

## Graph wiring

`graphData.ts`: drop `synthMastery`; fetch `/students/me/mastery`; set each node's ring from `by_node[id]`,
or a distinct **"no data"** style when absent. `page.tsx`: `mastery` and `bkt` toggles both show real
`p(known)`; `dkt` shows a "preview — трек D2" badge instead of a fabricated value.

## Dreaming integration

`DreamingService.dream_from_rows` computes mastery (same `MasteryService`) for the student and passes it to
`ReflectionGenerator.reflect(digests, mastery=...)`. The prompt gains a compact block:
`Текущее мастерство (BKT): <topic> p(known)=0.42 (n=7) …`, so the reflection cross-references claimed gaps
against the model's estimate.

## Signal robustness & edge cases

- No sessions / no graded outcomes → empty mastery (`{topics: [], by_node: {}}`), endpoint still 200; graph all
  "no data". (Mirrors the dreaming empty-student path.)
- Topic appears in many sessions → outcomes concatenated by time; single `StudentModel` accumulates.
- Anonymous and authenticated handled identically via the `student_default`/`user.id` resolution already used by `/dream`.
- Pure read path; safe to call repeatedly. No PII logged.

## Testing

- **Unit (`MasteryService`):** (1) replay a known correct/incorrect sequence → assert monotonic BKT `p_known`
  in expected band; (2) `is_correct`-null fallback to session-level outcome; (3) slug mapping
  matched/unmatched/normalization; (4) empty input → empty result.
- **Endpoint:** anonymous `GET /students/me/mastery` → 200 with `{topics, by_node}` keys.
- **Frontend:** `npx tsc --noEmit` exit 0; live check — a practiced topic lights its node, unpracticed shows "no data".

## Deferred (out of scope for D1 → D2 / later)

DKT-LSTM inference surfaced on the graph; Ebbinghaus decay-on-read (engine has `calculate_decay_factor` — cheap
follow-up); mastery caching; attention-based KT (SAKT/AKT); affect (RuBERT) and cognitive-load model upgrades;
explicit per-node skill tagging (slug mapping suffices for v1).

## Open items to confirm during planning

1. How densely `MessageTable.is_correct` is populated in live sessions (decides primary vs fallback signal weight).
2. Exact session→topic resolution reuse (share a helper with the dreaming digest to avoid drift).
3. Whether `get_knowledge_state` is best rewired in the orchestrator or the endpoint queries the DB directly.
