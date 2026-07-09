# Dreaming — file-memory session consolidation

**Status:** design approved (2026-05-31) · **Track:** C (of A delete-sessions / B graph-buttons / C dreaming / D model-upgrades)
**Branch:** 019-ns-vstar-dpo

## 1. Problem & intent

After tutoring sessions, MITS already grows the Knowledge Forge graph *synchronously and conservatively* (`SessionAnalyzer → ProposalQueue → GraphEvolver`). It does **not** step back to reflect on a student's learning, and nothing personalizes future sessions from past ones.

We add a **"dreaming"** capability: when the student's attention bottoms out (engagement-minimum) or they go idle, the system offers a rest and runs a background **"sleep" pass** that consolidates recent sessions into:
1. **Graph growth** (reusing the existing evolver), and
2. **Per-student markdown reflection files** — a `/memory`-style store, modeled on Anthropic's **Claude memory tool** (client-side file CRUD persisting across sessions) — which the tutor later **reads** to personalize.

This mirrors "sleep-time compute" / Generative-Agents *reflections*: heavy consolidation moved out of the user-latency window, synthesizing experience into higher-level notes that guide future behavior.

### Goals
- Trigger on the **existing engagement sensor** (`CognitiveLoadEstimator.should_offer_break`, affect = BORED) **and** on **idle** (new), plus a manual entry point.
- Reuse existing graph-growth; **do not** reimplement it.
- Produce durable, human-readable reflections the tutor consumes (feedback loop).
- Run offline (background), failure-isolated, idempotent.

### Non-goals (explicitly out of scope)
- **Track D** — upgrading the auxiliary models (BKT/DKT, cognitive-load, affect) to SOTA. Dreaming consumes the *current* signals.
- Real per-student BKT/DKT on the graph badges (that is the B1 follow-up in D).
- Cross-student / global consolidation. Dreaming is **per-student**.
- Scheduled/cron batch dreaming (the chosen trigger is engagement/idle + manual).

## 2. Architecture — components (isolated units)

| Unit | File | Responsibility | Depends on |
|---|---|---|---|
| `StudentMemoryFiles` | `src/memory/memory_files.py` | Per-student `/memory` dir CRUD (the Claude-style store) | stdlib only |
| `ReflectionGenerator` | `src/agents/reflection.py` | LLM: session data + existing memory → new reflection + profile update | LLMClient, StudentMemoryFiles |
| `DreamingService` | `backend/app/services/dreaming_service.py` | Orchestrate one sleep: consolidate graph + reflect → dream report | SessionAnalyzer/GraphEvolver, ReflectionGenerator, session storage |
| Dream endpoint + WS | `backend/app/api/v1/dream.py`, `websocket.py` | `POST /api/v1/dream`; WS `suggest_rest` event | DreamingService |
| Trigger (idle + engagement) | `orchestrator_service.py`, frontend idle timer | Emit `suggest_rest`; manual button | CognitiveLoadEstimator (exists) |
| Memory read-back | `orchestrator_service.py` (+ optional memory tools) | Inject latest reflection into guided system context | StudentMemoryFiles |
| UI: dreams panel + rest prompt | `frontend/src/...` | List past dreams + rendered reflection; in-chat rest prompt | api client |

### 2.1 `StudentMemoryFiles` (the `/memory` store)
- Layout: `data/students/{student_id}/memory/`
  - `profile.md` — durable facts (strengths, recurring misconceptions, preferred difficulty, style). Overwritten/merged each dream.
  - `dreams/<ISO-timestamp>.md` — one reflection per sleep (append-only history).
  - `state.json` — `{ "last_dreamed_at": ISO, "sessions_seen": [ids] }` (idempotency marker).
- API: `list() -> [paths]`, `read(name) -> str`, `append(name, text)`, `write(name, text)`, `read_profile() -> str`. No DB; pure files (matches Claude's client-side memory model and is trivially inspectable for the diploma).
- Path safety: `student_id` sanitized; writes confined to the student's dir (no traversal).

### 2.2 `ReflectionGenerator`
- Input: recent session traces for the student (messages, move types, correctness, mastery deltas, cognitive-load/affect events, hint usage), **plus** current `profile.md`.
- LLM prompt → JSON: `{ reflection_md, profile_update_md, next_focus: [topics], misconceptions: [..] }`.
- Writes `dreams/<ts>.md` (the reflection) and merges `profile_update_md` into `profile.md`.
- Wrapped in try/except; on LLM failure, writes a minimal heuristic summary (counts, topics, success rate) so a dream always produces *something*.

### 2.3 `DreamingService.dream(student_id) -> DreamReport`
1. Load sessions since `state.last_dreamed_at` (skip if none → no-op, idempotent).
2. **Consolidate graph**: feed traces through the existing `SessionAnalyzer → ProposalQueue → GraphEvolver` (no new graph logic).
3. **Reflect**: `ReflectionGenerator` over those sessions + memory files.
4. Update `state.json`.
5. Return `DreamReport { graph_changes: {nodes_added, edges_added, proposals}, reflection_excerpt, files_updated, sessions_count }`.
- Executed via FastAPI background task / asyncio so the request returns immediately; progress optionally streamed over WS.

### 2.4 Trigger
- **Engagement-minimum**: the guided pipeline already computes `should_offer_break` (cognitive load OVERLOAD/HIGH) and affect BORED. When set, the orchestrator emits a WS event `suggest_rest { reason }` after the tutor turn.
- **Idle**: a frontend idle timer (no keypress/activity for `IDLE_MS`, default ~3 min) emits the same in-chat prompt.
- **Manual**: a "Сон" button (dashboard/graph rail) for control and demo.
- Prompt UX: a gentle card — *"Хочешь передохнуть? Я пока обдумаю твои сессии."* → **Accept** → `POST /api/v1/dream` → background dream → toast/report when done.

### 2.5 Feedback loop (the Claude-like part)
- At **session start** (and on mode switch to guided), the orchestrator reads `profile.md` and injects a compact summary into the guided system context (reliable, deterministic).
- **Stretch**: expose `list_memory` / `read_memory` as agent tools (like source_tools) so the tutor can pull specific past reflections on demand — true Claude-memory-tool parity. Auto-inject ships first; tools are additive.

### 2.6 UI
- **Dreams panel** (dashboard or graph right-rail): list past dreams (timestamp + one-line summary) → click → rendered reflection markdown (reuses `SmartContent`).
- **Rest prompt** in chat from `suggest_rest`.
- Dream-grown graph nodes already surface via Forge; optional "new from dream" hint.

## 3. Data flow

```
sessions (SQLite) + mastery (StudentMemory) + cognitive-load/affect events
        │
        ▼
   DreamingService.dream(student_id)
        ├── SessionAnalyzer → ProposalQueue → GraphEvolver → forge.json   (graph grows)
        └── ReflectionGenerator (LLM) → data/students/{id}/memory/*.md     (reflections)
        ▼
   DreamReport → UI (dreams panel) + WS toast
        ▲
guided session start ── reads profile.md ──► injected into tutor system context (personalization)
```

## 4. Error handling & safety
- Dreaming runs in the background; a failure never breaks an active session (logged, surfaced as a soft toast).
- LLM reflection failure → heuristic fallback summary.
- Idempotent: `state.last_dreamed_at` + `sessions_seen` prevent re-processing.
- No PII leakage beyond what's already in sessions; files live under the student's own dir; path-traversal guarded.
- Per-user isolation consistent with existing source ownership.

## 5. Testing
- `StudentMemoryFiles`: CRUD round-trip, path-traversal rejection, missing-file reads.
- `ReflectionGenerator`: mock LLM → asserts a `dreams/*.md` is written and `profile.md` merged; fallback path on LLM error.
- `DreamingService`: with stub session data → asserts graph-grow invoked + reflection saved + idempotent no-op on second run.
- Trigger: engagement-min/idle → `suggest_rest` emitted; `POST /dream` endpoint returns a report.
- Frontend: idle timer fires prompt; dreams panel renders.

## 6. Rollout
1. `StudentMemoryFiles` + tests.
2. `ReflectionGenerator` + tests (mock LLM).
3. `DreamingService` (reuse evolver) + endpoint + tests.
4. Trigger (WS `suggest_rest` + idle timer + manual button).
5. Memory read-back injection at session start.
6. UI dreams panel + rest prompt.
7. (Stretch) memory agent-tools.

Each step is independently testable; live verification per step (mirrors how A/B/streaming/theme were verified).
