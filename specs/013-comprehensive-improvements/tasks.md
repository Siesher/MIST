# Tasks: MITS Comprehensive Improvements

**Input**: Design documents from `/specs/013-comprehensive-improvements/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.yaml, quickstart.md

**Organization**: Tasks grouped by user story for independent implementation. 12 user stories across 3-month timeline.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, database layer, and shared utilities needed by multiple stories

- [x] T001 Add new Python dependencies (sqlalchemy, alembic, PyJWT, argon2-cffi, weasyprint, matplotlib) to backend/requirements.txt
- [x] T002 [P] Add new frontend dependencies (recharts, react-activity-calendar, date-fns) to frontend/package.json and run npm install
- [x] T003 [P] Create SQLAlchemy engine and async session factory in backend/app/models/database.py
- [x] T004 Initialize Alembic migration framework in backend/migrations/ with alembic.ini config
- [x] T005 Create ORM models (UserTable, SessionTable, MessageTable, RefreshTokenTable) in backend/app/models/tables.py based on data-model.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Session persistence and authentication — MUST complete before user stories

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create first Alembic migration for users, sessions, messages, refresh_tokens tables in backend/migrations/versions/
- [x] T007 Migrate OrchestratorService session storage from in-memory dict to SQLAlchemy in backend/app/services/orchestrator_service.py — create_session, get_session, process_message_stream must read/write to DB
- [x] T008 Migrate message storage to SQLAlchemy — all addMessage/getMessages operations in orchestrator_service.py must persist to messages table
- [x] T009 Create JWT utility module (create_access_token, create_refresh_token, verify_token, hash_password, verify_password) in backend/app/models/auth.py using PyJWT + Argon2
- [x] T010 Create auth API endpoints (POST /register, /login, /refresh, /logout) in backend/app/api/v1/auth.py
- [x] T011 Create FastAPI dependency `get_current_user` for protected endpoints in backend/app/api/v1/auth.py
- [x] T012 Add auth middleware to existing session/chat/hint endpoints — pass user_id from JWT to orchestrator in backend/app/api/v1/sessions.py and backend/app/api/v1/websocket.py
- [x] T013 Add WebSocket authentication — verify JWT token on connection (query param or first message) in backend/app/api/v1/websocket.py
- [x] T014 [P] Create login page in frontend/src/app/auth/login/page.tsx with email/password form
- [x] T015 [P] Create registration page in frontend/src/app/auth/register/page.tsx
- [x] T016 Create AuthProvider context with token storage and refresh logic in frontend/src/components/auth/AuthProvider.tsx and frontend/src/lib/auth.ts
- [x] T017 Add auth guards — redirect unauthenticated users to /auth/login, pass Authorization header in API calls in frontend/src/lib/api.ts
- [x] T018 Update frontend/src/hooks/useWebSocket.ts to include JWT token in WebSocket connection URL

**Checkpoint**: Sessions persist across restarts. Users register/login. Data is isolated per user.

---

## Phase 3: User Story 1 — Fine-tuned Tutoring Model (Priority: P1) MVP

**Goal**: Fine-tune GLM-4.7-Flash on Socratic tutoring dialogs using QLoRA on Colab A100

**Independent Test**: Run evaluation comparing base vs fine-tuned model on 100 test dialogs. Fine-tuned Socratic Score should be higher.

### Implementation for User Story 1

- [x] T019 [US1] Create synthetic dialog generation notebook in notebooks/synthetic_dialogs.ipynb — prompt templates for 5 topics × 4 difficulties × 5 student types, output to data/training/synthetic_dialogs.jsonl
- [x] T020 [US1] Create dialog annotation schema and validation script in training/dataset/dialog_schema.py — validate move_type, emotion, error_type, is_correct fields per turn
- [x] T021 [US1] Create quality filtering pipeline in training/dataset/quality_filter.py — min 10 turns, balanced speaker ratio, no answer leaks, LLM cross-verification scoring
- [x] T022 [US1] Create ChatML formatter that converts synthetic dialogs to Unsloth training format in training/scripts/prepare_chatml.py
- [x] T023 [US1] Create QLoRA fine-tuning notebook in notebooks/finetuning_glm.ipynb — Unsloth + TRL SFTTrainer, checkpoint saving per epoch, Colab A100 compatible
- [x] T024 [US1] Create LoRA-to-GGUF export script in training/scripts/export_lora_gguf.py — convert adapter weights, generate Ollama Modelfile with ADAPTER instruction
- [x] T025 [US1] Create integration script to load fine-tuned model into Ollama in training/scripts/deploy_finetuned.sh — `ollama create mits-tutor-ft -f Modelfile`
- [x] T026 [US1] Add model selection config to backend — switch between base and fine-tuned model via environment variable in src/config.py and backend/app/services/orchestrator_service.py

**Checkpoint**: Fine-tuned model deployed in Ollama. System uses it for tutoring. Can compare with base model.

---

## Phase 4: User Story 2 — Trained Knowledge Tracing (Priority: P1)

**Goal**: Pre-train DKT on ASSISTments dataset, integrate trained weights into production knowledge tracker

**Independent Test**: DKT achieves AUC > 0.75 on test set. BKT vs DKT comparison report generated.

### Implementation for User Story 2

- [x] T027 [US2] Create ASSISTments data download and preprocessing script in training/scripts/prepare_assistments.py — download, remove scaffolding, skill mapping, sequence creation, train/val/test split
- [x] T028 [US2] Create DKT training notebook in notebooks/dkt_training.ipynb — LSTM training on ASSISTments, hyperparameter config, validation AUC tracking, checkpoint saving
- [x] T029 [US2] Create DKT weight export script that saves trained weights compatible with src/models/dkt_model.py in training/scripts/export_dkt_weights.py
- [x] T030 [US2] Update src/models/dkt_model.py to load pre-trained weights from data/models/dkt_pretrained.pt on initialization
- [x] T031 [US2] Update src/models/knowledge_tracing.py to use pre-trained DKT for students with >10 interactions, BKT for new students

**Checkpoint**: DKT loaded with trained weights. Knowledge tracker uses hybrid BKT+DKT based on student history.

---

## Phase 5: User Story 3 — ML-based Emotion Detection (Priority: P1)

**Goal**: Replace rule-based affective detector with fine-tuned RuBERT classifier

**Independent Test**: ML detector achieves macro F1 > 0.65 on test set, higher than rule-based baseline.

### Implementation for User Story 3

- [x] T032 [US3] Create emotion dataset generator that labels messages using existing rule-based detector in training/scripts/generate_affect_labels.py — export from MITS sessions, target 3000-5000 labeled examples
- [x] T033 [US3] Create RuBERT fine-tuning notebook in notebooks/affective_rubert.ipynb — DeepPavlov/rubert-base-cased, 5-class classification, train/val/test split, F1 tracking
- [x] T034 [US3] Create model export script that saves fine-tuned RuBERT weights to data/models/rubert_affect/ in training/scripts/export_rubert.py
- [x] T035 [US3] Create ML-based AffectiveDetector class in src/models/affective_ml_detector.py — load RuBERT, predict emotion from text, return confidence scores
- [x] T036 [US3] Update src/agents/affective_agent.py to support both rule-based and ML-based detectors via config switch (AFFECT_DETECTOR_TYPE=rules|ml in src/config.py)

**Checkpoint**: ML affect detector integrated. Config switch toggles between rules and ML. Both can run for comparison.

---

## Phase 6: User Story 4 — Evaluation Pipeline (Priority: P1)

**Goal**: Automated benchmarks producing comparison tables for the diploma thesis

**Independent Test**: Run full evaluation suite, verify structured report with all metrics generated.

### Implementation for User Story 4

- [x] T037 [US4] Create Socratic Score benchmark in evaluation/benchmarks/socratic_score.py — analyze tutor responses for guiding questions vs direct answers, compute Socratic Score and Telling Rate
- [x] T038 [P] [US4] Create Error Recovery benchmark in evaluation/benchmarks/error_recovery.py — measure % of student errors successfully corrected within 3 turns
- [x] T039 [P] [US4] Create latency benchmark in evaluation/benchmarks/latency_benchmark.py — measure response time per mode (chat, guided_learning, task_generator), with/without cache
- [x] T040 [US4] Create knowledge prediction benchmark in evaluation/benchmarks/knowledge_prediction.py — compute AUC, RMSE, accuracy for BKT and DKT on test data
- [x] T041 [US4] Create affect detection benchmark in evaluation/benchmarks/affect_accuracy.py — compute per-class F1, precision, recall for rules vs ML detector
- [x] T042 [US4] Create base vs fine-tuned model comparison script in evaluation/comparisons/base_vs_finetuned.py — run both models on same test dialogs, compare all metrics
- [x] T043 [US4] Create unified evaluation runner in evaluation/run_benchmarks.py — CLI that runs selected or all benchmarks, outputs structured JSON + markdown report to evaluation/reports/
- [x] T044 [US4] Create report generator that formats benchmark results as markdown tables suitable for thesis in evaluation/comparisons/generate_report.py

**Checkpoint**: `python -m evaluation.run_evaluation --benchmark all` produces complete report with all comparison tables.

---

## Phase 7: User Story 5 — Handwritten Solution Recognition (Priority: P2)

**Goal**: Upload photo of handwritten math → OCR to LaTeX → verify with SymPy

**Independent Test**: Upload 10 handwritten solution photos, verify at least 7 correctly recognized.

### Implementation for User Story 5

- [x] T045 [US5] Update src/models/vision_analyzer.py to use Qwen2.5-VL-7B via Ollama — send base64 image with LaTeX extraction prompt, parse response
- [x] T046 [US5] Create SymPy verification pipeline in src/models/solution_verifier.py — parse LaTeX to SymPy expressions, compare steps against expected answer, identify first error
- [x] T047 [US5] Create vision API endpoint POST /api/v1/vision/recognize and POST /api/v1/vision/verify in backend/app/api/v1/vision.py
- [x] T048 [US5] Create ImageUpload component in frontend/src/components/chat/ImageUpload.tsx — camera/file input, preview, upload to backend
- [x] T049 [US5] Integrate ImageUpload into ChatInput — add camera button, display OCR result as message in frontend/src/components/chat/ChatInput.tsx
- [x] T050 [US5] Add image_upload WebSocket message type handling in backend/app/api/v1/websocket.py — receive base64, run OCR, send ocr_result back

**Checkpoint**: Student uploads handwritten solution photo → system recognizes LaTeX → verifies each step → provides feedback.

---

## Phase 8: User Story 6 — A/B Experiment Framework (Priority: P2)

**Goal**: Controlled experiment comparing Socratic vs direct answer modes on real students

**Independent Test**: Create experiment, enroll 2 test users, submit pre/post scores, verify statistical report.

### Implementation for User Story 6

- [x] T051 [US6] Create Experiment and ExperimentParticipant ORM models in backend/app/models/tables.py, add Alembic migration
- [x] T052 [US6] Create experiment service in backend/app/services/experiment_service.py — create experiment, enroll participants, random group assignment, record scores
- [x] T053 [US6] Create statistical analysis module in evaluation/experiment_analysis.py — compute group means, t-test, Cohen's d, confidence intervals
- [x] T054 [US6] Create experiment API endpoints (POST /experiments, /enroll, /pre-test, /post-test, GET /results) in backend/app/api/v1/experiments.py
- [x] T055 [US6] Integrate experiment group assignment with session creation — when enrolled student creates session, force mode from experiment config in backend/app/services/orchestrator_service.py

**Checkpoint**: Full experiment lifecycle works. Statistical report generated with p-value and effect size.

---

## Phase 9: User Story 7 — Student Analytics Dashboard (Priority: P2)

**Goal**: Interactive dashboard with mastery charts, activity heatmap, error distribution, recommendations

**Independent Test**: Open dashboard for student with 10+ sessions, verify all 4 visualizations render.

### Implementation for User Story 7

- [x] T056 [US7] Create analytics aggregation service in backend/app/services/analytics_service.py — compute mastery_by_topic, activity_by_day, error_distribution, ZPD recommendations from session/message data
- [x] T057 [US7] Create analytics API endpoints (GET /analytics/activity, /performance, /mastery, /errors) in backend/app/api/v1/analytics.py
- [x] T058 [P] [US7] Create MasteryChart component (Recharts LineChart) in frontend/src/components/analytics/MasteryChart.tsx — mastery per topic over time
- [x] T059 [P] [US7] Create ActivityHeatmap component (react-activity-calendar) in frontend/src/components/analytics/ActivityHeatmap.tsx — GitHub-style contribution heatmap
- [x] T060 [P] [US7] Create ErrorDistribution component (Recharts PieChart) in frontend/src/components/analytics/ErrorDistribution.tsx — error types breakdown
- [x] T061 [P] [US7] Create Recommendations component in frontend/src/components/analytics/Recommendations.tsx — ZPD-based topic suggestions with priority indicators
- [x] T062 [US7] Create analytics dashboard page in frontend/src/app/dashboard/page.tsx — compose all 4 chart components, fetch data from analytics API

**Checkpoint**: Dashboard renders all 4 visualizations with real student data. Recommendations based on ZPD.

---

## Phase 10: User Story 8 — Optimization Module Integration (Priority: P2)

**Goal**: Wire existing cache/prefetcher/compressor modules into orchestrator, measure latency improvement

**Independent Test**: Same question twice → second response 70%+ faster. Average latency reduced 30%+ across 50 requests.

### Implementation for User Story 8

- [x] T063 [US8] Create LLM response cache service in backend/app/services/cache_service.py — in-memory LRU dict keyed by (prompt_hash, mode), configurable max size, TTL
- [x] T064 [US8] Integrate cache into process_message_stream in backend/app/services/orchestrator_service.py — check cache before LLM call, store response after streaming completes
- [x] T065 [US8] Wire hint prefetcher (src/inference/hint_prefetcher.py) into orchestrator — trigger background hint computation on task assignment using FastAPI BackgroundTasks
- [x] T066 [US8] Wire context compressor (src/inference/context_compressor.py) into process_message_stream — compress history when >10 messages, keep last 5 + key events summary
- [x] T067 [US8] Create performance metrics endpoint GET /api/v1/metrics in backend/app/api/v1/analytics.py — report cache hit rate, avg latency, token savings

**Checkpoint**: Repeated queries served from cache. Hints pre-computed. Long conversations compressed. Latency benchmark shows 30%+ improvement.

---

## Phase 11: User Story 9 — Progress Export (Priority: P3)

**Goal**: Student exports learning progress as PDF report

**Independent Test**: Generate PDF for student with 5+ sessions, verify all sections present.

### Implementation for User Story 9

- [x] T068 [US9] Create PDF report HTML template with Jinja2 in backend/app/templates/report.html — student summary, session list, mastery chart, error types, recommendations
- [x] T069 [US9] Create export service in backend/app/services/export_service.py — gather student data, render matplotlib charts to base64 PNG, render Jinja2 template, convert to PDF with WeasyPrint
- [x] T070 [US9] Create export endpoint GET /api/v1/export/report.pdf in backend/app/api/v1/export.py — stream PDF response with Content-Disposition header
- [x] T071 [US9] Add "Export Progress" button to frontend profile/dashboard page that downloads PDF in frontend/src/app/dashboard/page.tsx

**Checkpoint**: Student clicks export → PDF downloads with summary, charts, and recommendations.

---

## Phase 12: User Story 10 — Session Persistence Validation (Priority: P3)

**Goal**: Verify all sessions and messages survive server restarts with zero data loss

**Independent Test**: Create session, send messages, restart server, reload page — all messages preserved.

*Note: Core persistence implemented in Phase 2 (T007-T008). This phase validates and hardens.*

### Implementation for User Story 10

- [x] T072 [US10] Add session restore logic to frontend — on page load, fetch session from API and restore full message history in frontend/src/app/chat/[sessionId]/page.tsx (verify existing logic works with persisted data)
- [x] T073 [US10] Add auto-save for session state (hints_used, attempts, is_solved) on every state change in backend/app/services/orchestrator_service.py
- [x] T074 [US10] Run quickstart.md Test 1 (Session Persistence) — create session, send messages, restart server, verify all data preserved

**Checkpoint**: Zero data loss across server restarts confirmed.

---

## Phase 13: User Story 11 — Authentication Validation (Priority: P3)

**Goal**: Confirm multi-user isolation and auth flows work correctly

*Note: Core auth implemented in Phase 2 (T009-T018). This phase validates edge cases.*

### Implementation for User Story 11

- [x] T075 [US11] Test user data isolation — register 2 users, create sessions for each, verify neither sees the other's sessions via GET /api/v1/sessions
- [x] T076 [US11] Test token refresh flow — wait for access token expiry, verify refresh produces new valid tokens
- [x] T077 [US11] Test WebSocket auth — verify unauthenticated WebSocket connections are rejected

**Checkpoint**: Multi-user isolation confirmed. Token refresh works. Unauthorized access blocked.

---

## Phase 14: User Story 12 — Docker Deployment (Priority: P3)

**Goal**: Single-command deployment with Docker Compose

**Independent Test**: On clean machine, `docker compose up` → all services start → chat works within 5 minutes.

### Implementation for User Story 12

- [x] T078 [US12] Create backend Dockerfile (multi-stage: base → dev → prod) in backend/Dockerfile
- [x] T079 [P] [US12] Create frontend Dockerfile (multi-stage: deps → build → serve) in frontend/Dockerfile
- [x] T080 [US12] Create docker-compose.yml at project root with 3 services (ollama with GPU passthrough, backend, frontend), volumes for models and data
- [x] T081 [US12] Create .env.docker with default environment variables for Docker deployment
- [x] T082 [US12] Add model pull initialization — ensure GLM-4.7-Flash is pulled on first ollama start via entrypoint script
- [x] T083 [US12] Run quickstart.md Test 10 (Docker Deployment) — `docker compose up`, verify full system works

**Checkpoint**: `docker compose up` starts all services. New user can register, chat, and get streamed responses.

---

## Phase 15: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation, and validation

- [x] T084 Update README.md with new features: authentication, analytics dashboard, Docker deployment, evaluation pipeline
- [x] T085 [P] Update backend/requirements.txt and frontend/package.json to pin all dependency versions
- [x] T086 Run quickstart.md full smoke test — execute all 12 validation tests
- [x] T087 Generate final evaluation report with all comparisons (base vs fine-tuned, BKT vs DKT, rules vs ML affect)
- [x] T088 [P] Clean up unused code and imports across modified files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 Fine-tuning (Phase 3)**: After Phase 2 — can run in parallel with US2, US3 (Colab work)
- **US2 DKT Training (Phase 4)**: After Phase 2 — can run in parallel with US1, US3 (Colab work)
- **US3 ML Affect (Phase 5)**: After Phase 2 — can run in parallel with US1, US2 (Colab work)
- **US4 Evaluation (Phase 6)**: After US1, US2, US3 — needs trained models for comparison
- **US5 Vision (Phase 7)**: After Phase 2 — independent of other stories
- **US6 A/B Experiment (Phase 8)**: After Phase 2 — needs auth for multi-user
- **US7 Dashboard (Phase 9)**: After Phase 2 — needs persisted data for analytics
- **US8 Optimization (Phase 10)**: After Phase 2 — independent
- **US9 Export (Phase 11)**: After US7 — reuses analytics data
- **US10-11 Validation (Phase 12-13)**: After Phase 2 — validates foundational work
- **US12 Docker (Phase 14)**: After all stories — packages everything
- **Polish (Phase 15)**: After all desired stories complete

### Month-by-Month Execution

**Month 1 (Weeks 1-4)**: Setup + Foundation + Colab Training
```
Week 1-2: Phase 1 (Setup) + Phase 2 (Foundation: DB, Auth)
Week 2-4: Phase 3 (US1 Fine-tuning) || Phase 4 (US2 DKT) || Phase 5 (US3 Affect)
          — All three run in parallel on Colab
```

**Month 2 (Weeks 5-8)**: ML Integration + Features
```
Week 5-6: Phase 6 (US4 Evaluation) — needs trained models from Month 1
Week 6-7: Phase 7 (US5 Vision) || Phase 8 (US6 A/B Experiment) — parallel
Week 7-8: Phase 9 (US7 Dashboard) || Phase 10 (US8 Optimization) — parallel
```

**Month 3 (Weeks 9-12)**: Production + Polish + Thesis
```
Week 9:   Phase 11 (US9 Export) + Phase 12-13 (Validation)
Week 10:  Phase 14 (US12 Docker)
Week 11:  Phase 15 (Polish) + Final evaluation report
Week 12:  Thesis writing + presentation preparation
```

### Parallel Opportunities

Within Phase 2 (Foundation):
```
T014 (login page) || T015 (register page) — different files
T009 (JWT utils) || T003 (SQLAlchemy) — different modules
```

Month 1 Colab training (after Phase 2):
```
US1 (Fine-tuning notebook) || US2 (DKT notebook) || US3 (RuBERT notebook) — independent Colab notebooks
```

Month 2 Features:
```
US5 (Vision) || US6 (A/B Experiment) || US7 (Dashboard) || US8 (Optimization) — independent features
```

Within US7 (Dashboard):
```
T058 (MasteryChart) || T059 (ActivityHeatmap) || T060 (ErrorDistribution) || T061 (Recommendations) — different component files
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3)

1. Complete Phase 1: Setup (dependencies, DB layer)
2. Complete Phase 2: Foundation (persistence, auth) — CRITICAL
3. Complete Phase 3: US1 (fine-tuning) — produces trained model
4. **STOP and VALIDATE**: Server restarts preserve data, auth works, fine-tuned model deployed
5. This alone delivers significant academic value

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready (persistent DB, auth)
2. Add US1-US3 → Three trained ML models (fine-tuned LLM, DKT, RuBERT)
3. Add US4 → Evaluation pipeline with comparison tables
4. Add US5-US8 → Vision, A/B framework, dashboard, optimizations
5. Add US9-US12 → Export, validation, Docker
6. Phase 15 → Polish and final report

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Total: 88 tasks across 15 phases
- Month 1: Foundation + Colab training (3 notebooks in parallel)
- Month 2: Integration + New features (4 independent feature tracks)
- Month 3: Production hardening + Evaluation + Thesis
- Colab notebooks are self-contained — can be developed independently of backend/frontend
- All infrastructure changes maintain backward compatibility with existing 012-chat-modes functionality
