# Feature Specification: MITS Comprehensive Improvements

**Feature Branch**: `013-comprehensive-improvements`
**Created**: 2026-02-05
**Status**: Draft
**Input**: Three-month improvement plan for MITS with Colab Pro+ (A100 GPU) for ML training

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fine-tuned Tutoring Model (Priority: P1)

A researcher fine-tunes the GLM language model on Socratic tutoring dialogs to improve the quality of guided learning responses. The system generates a synthetic dataset of 1000+ annotated tutoring dialogs, trains the model using QLoRA on Colab Pro+, and integrates the fine-tuned weights back into the production system. The researcher can compare base vs fine-tuned model performance using automated metrics.

**Why this priority**: The language model is the core of the entire system. Improving its tutoring ability directly impacts every user interaction and produces the strongest academic results for the diploma.

**Independent Test**: Run the evaluation pipeline on 100 test dialogs comparing base GLM vs fine-tuned GLM. Measure Socratic Score (% of responses with guiding questions) and Telling Rate (% of direct answers). Fine-tuned model should score higher on Socratic Score and lower on Telling Rate.

**Acceptance Scenarios**:

1. **Given** an empty training pipeline, **When** the researcher runs the synthetic data generator with parameters (5 topics, 4 difficulties, 5 student types), **Then** at least 1000 annotated dialogs are produced with fields: move_type, is_correct, emotion, error_type
2. **Given** the synthetic dataset and MathDial data, **When** the researcher runs QLoRA fine-tuning on Colab Pro+ A100, **Then** training completes within 24 hours and produces exportable LoRA weights
3. **Given** fine-tuned weights, **When** the weights are loaded into the production Ollama deployment, **Then** the tutoring system uses the fine-tuned model without changes to the application code
4. **Given** base and fine-tuned models, **When** the evaluation pipeline runs on 100 test dialogs, **Then** a comparison report is generated showing Socratic Score, Telling Rate, and response quality metrics

---

### User Story 2 - Trained Knowledge Tracing (Priority: P1)

A researcher pre-trains the Deep Knowledge Tracing (DKT) LSTM model on large-scale educational datasets (ASSISTments, EdNet) so the system can accurately predict student mastery from interaction history. The pre-trained model is exported and integrated into the existing hybrid BKT+DKT knowledge tracker.

**Why this priority**: Knowledge tracing drives adaptive task selection (ZPD). Without trained weights, the DKT component operates on random initialization, making it no better than the simpler BKT baseline. Training on real data enables meaningful academic comparison.

**Independent Test**: Train DKT on ASSISTments 2009 dataset, evaluate on held-out test set. Report AUC, RMSE, and accuracy. Compare with BKT baseline. DKT should achieve AUC > 0.75.

**Acceptance Scenarios**:

1. **Given** the ASSISTments 2009 dataset downloaded and preprocessed, **When** the DKT training notebook runs on Colab A100, **Then** training completes and produces model weights with validation AUC > 0.75
2. **Given** trained DKT weights, **When** they are loaded into the production knowledge tracker, **Then** the system uses DKT predictions for students with sufficient history (>10 interactions)
3. **Given** both BKT and trained DKT, **When** the evaluation runs on test data, **Then** a comparison report shows AUC, RMSE, and accuracy for both models

---

### User Story 3 - ML-based Emotion Detection (Priority: P1)

A researcher replaces the rule-based affective detector (27 keyword patterns) with a fine-tuned language model (RuBERT) that classifies student emotions from text messages. The ML model detects 5 emotional states (frustrated, confused, engaged, bored, neutral) with higher accuracy than rules.

**Why this priority**: Affective computing is a key innovation of the system. Replacing rules with ML produces measurable improvement and a strong experimental comparison for the diploma.

**Independent Test**: Evaluate rule-based vs ML detector on a labeled test set of 200+ messages. Compare F1-score per emotion class. ML model should achieve macro F1 > 0.65.

**Acceptance Scenarios**:

1. **Given** a labeled dataset of 1000+ student messages with emotion annotations, **When** RuBERT is fine-tuned on Colab A100, **Then** the model achieves macro F1 > 0.65 on a held-out test set
2. **Given** the trained emotion classifier, **When** it is integrated into the affective agent, **Then** the system uses ML predictions instead of keyword rules at runtime
3. **Given** both rule-based and ML detectors, **When** the evaluation runs on the same test set, **Then** a comparison report shows per-class precision, recall, and F1 for both approaches

---

### User Story 4 - Evaluation Pipeline (Priority: P1)

A researcher runs automated benchmarks that measure the entire system's performance across multiple dimensions: tutoring quality, knowledge prediction accuracy, emotion detection accuracy, and response latency. The pipeline produces comparison tables suitable for inclusion in the diploma thesis.

**Why this priority**: Without quantitative evaluation, the diploma lacks scientific rigor. The evaluation pipeline transforms the project from "I built a system" into "The system achieved X% improvement."

**Independent Test**: Run the full evaluation suite and verify it produces a structured report with all metrics populated and comparison tables generated.

**Acceptance Scenarios**:

1. **Given** the evaluation pipeline configured with test data, **When** the researcher runs the benchmark suite, **Then** it produces metrics: Socratic Score, Telling Rate, Error Recovery Rate, Affective Accuracy, average response latency
2. **Given** base and fine-tuned models available, **When** the comparison benchmark runs, **Then** a side-by-side report is generated showing all metrics for both models
3. **Given** BKT and DKT models available, **When** the knowledge tracing benchmark runs, **Then** AUC, RMSE, and accuracy are reported for both
4. **Given** rule-based and ML affect detectors, **When** the affect benchmark runs, **Then** per-class F1, precision, recall are reported for both

---

### User Story 5 - Handwritten Solution Recognition (Priority: P2)

A student photographs their handwritten math solution and uploads it. The system recognizes the mathematical expressions, converts them to LaTeX, verifies correctness step-by-step using a computer algebra system, and provides feedback on errors.

**Why this priority**: Multimodal AI tutoring is a cutting-edge research topic. This feature demonstrates the system's ability to handle real-world student inputs beyond text chat.

**Independent Test**: Upload 10 photos of handwritten solutions. Verify that at least 7 are correctly recognized and verified.

**Acceptance Scenarios**:

1. **Given** a photo of a handwritten derivative solution, **When** the student uploads it via the chat interface, **Then** the system extracts LaTeX notation and displays it for confirmation
2. **Given** extracted LaTeX, **When** the verification engine runs, **Then** each step is checked against the correct solution and errors are highlighted
3. **Given** an incorrect handwritten step, **When** verification detects the error, **Then** the tutor provides Socratic guidance to help the student find the mistake

---

### User Story 6 - A/B Experiment Framework (Priority: P2)

A researcher conducts a controlled experiment comparing Socratic tutoring (guided_learning mode) vs direct answers (chat mode) on a group of 20-30 students. The system administers pre-tests, tracks interactions across 3 sessions, administers post-tests, and generates statistical analysis.

**Why this priority**: Empirical user studies are the gold standard for ITS evaluation. This provides the strongest evidence of system effectiveness for the diploma.

**Independent Test**: Run a simulated experiment with synthetic student interactions and verify pre/post test scoring, group assignment, and statistical report generation.

**Acceptance Scenarios**:

1. **Given** an experiment configuration (2 groups, 3 sessions each), **When** students are enrolled, **Then** they are randomly assigned to guided_learning or chat group with balanced allocation
2. **Given** enrolled students, **When** they complete the pre-test, **Then** scores are recorded and baseline knowledge is established
3. **Given** completed pre and post tests, **When** the analysis runs, **Then** a statistical report is generated with: mean scores per group, score improvement (post - pre), t-test p-value, Cohen's d effect size

---

### User Story 7 - Student Analytics Dashboard (Priority: P2)

A student views their learning progress through an interactive dashboard showing skill mastery over time, activity heatmap, error type distribution, and personalized study recommendations based on the Zone of Proximal Development.

**Why this priority**: Visual analytics demonstrate the system's intelligence and provide compelling screenshots for the diploma presentation.

**Independent Test**: Open the dashboard for a student with 10+ completed sessions. Verify all four visualizations render with real data.

**Acceptance Scenarios**:

1. **Given** a student with interaction history, **When** they open the analytics dashboard, **Then** they see a line chart showing mastery progression per topic over time
2. **Given** session history, **When** the dashboard loads, **Then** an activity heatmap shows which days and times the student studied
3. **Given** error history, **When** the dashboard loads, **Then** a distribution chart shows error types (conceptual, procedural, careless, etc.)
4. **Given** current mastery levels, **When** the recommendation engine runs, **Then** it suggests 3 topics to study next based on ZPD (mastery 0.3-0.8)

---

### User Story 8 - Optimization Module Integration (Priority: P2)

The system integrates existing but unwired optimization modules (LLM response cache, hint prefetcher, context compressor) into the orchestrator service, measurably reducing response latency and token usage.

**Why this priority**: Demonstrates engineering maturity and provides before/after performance metrics for the diploma.

**Independent Test**: Send the same question twice. Verify the second response arrives significantly faster (cached). Measure average latency reduction across 50 requests.

**Acceptance Scenarios**:

1. **Given** LLM cache enabled, **When** the same question is asked twice, **Then** the second response is served from cache with latency < 100ms
2. **Given** hint prefetcher enabled, **When** a new task is assigned, **Then** hints are pre-computed in the background before the student requests them
3. **Given** context compressor enabled, **When** conversation history exceeds 10 messages, **Then** older messages are compressed to reduce token usage while preserving context
4. **Given** optimization modules active, **When** latency benchmarks run, **Then** average response time is reduced by at least 30% compared to baseline

---

### User Story 9 - Progress Export (Priority: P3)

A student exports their learning progress as a PDF report containing session summary, topic mastery, error patterns, and study recommendations. The report can be shared with instructors or used for self-assessment.

**Why this priority**: Tangible output artifact that can be demonstrated to the diploma committee.

**Independent Test**: Generate a PDF for a student with 5+ sessions. Verify it contains all required sections and renders correctly.

**Acceptance Scenarios**:

1. **Given** a student with session history, **When** they click "Export Progress", **Then** a PDF report is generated and downloaded
2. **Given** the generated PDF, **When** opened, **Then** it contains: student summary, session list, mastery chart per topic, common error types, and study recommendations

---

### User Story 10 - Session Persistence (Priority: P3)

All chat sessions, messages, and session state are persisted to a database so that data survives server restarts. Students can return to their previous conversations after the server is restarted.

**Why this priority**: Required for any real-world usage and for conducting the A/B experiment (multi-day sessions).

**Independent Test**: Create a session, send messages, restart the server, reload the page. Verify all messages are preserved.

**Acceptance Scenarios**:

1. **Given** an active session with messages, **When** the server restarts, **Then** all sessions and messages are restored from the database
2. **Given** a restored session, **When** the student sends a new message, **Then** the conversation continues with full history context

---

### User Story 11 - User Authentication (Priority: P3)

Students register and log in with credentials. Each student's data (sessions, progress, preferences) is isolated. Multiple students can use the system simultaneously without data leaks.

**Why this priority**: Required for multi-user A/B experiments and real-world deployment.

**Independent Test**: Register two users, create sessions for each, verify neither can see the other's data.

**Acceptance Scenarios**:

1. **Given** the registration page, **When** a new student registers with email and password, **Then** an account is created and the student is logged in
2. **Given** two authenticated students, **When** each views their sessions, **Then** they see only their own data
3. **Given** an unauthenticated request, **When** it accesses a protected endpoint, **Then** it receives an authentication error

---

### User Story 12 - Docker Deployment (Priority: P3)

The entire system (backend, frontend, LLM server) can be started with a single command using container orchestration. New developers or evaluators can run the system without manual setup.

**Why this priority**: Simplifies deployment for the diploma demonstration and makes the system reproducible.

**Independent Test**: Clone the repository on a clean machine, run the deployment command, verify the system starts and all three chat modes work.

**Acceptance Scenarios**:

1. **Given** a machine with container runtime installed, **When** the deployment command is run, **Then** all services start and the application is accessible in the browser
2. **Given** the running deployment, **When** a student creates a session and sends a message, **Then** they receive a streamed response from the LLM

---

### Edge Cases

- What happens when Colab session disconnects during training? (Checkpoint saving required)
- What happens when the fine-tuned model produces worse results than base? (Rollback mechanism needed)
- What happens when the vision model cannot recognize handwriting? (Graceful fallback to text input with error message)
- What happens when the database is corrupted? (Migration rollback, backup strategy)
- What happens when authentication token expires during a WebSocket session? (Token refresh or re-authentication prompt)
- What happens when the A/B experiment has unbalanced groups due to dropouts? (Statistical adjustments, intention-to-treat analysis)

## Requirements *(mandatory)*

### Functional Requirements

**Data & Training (Month 1)**
- **FR-001**: System MUST generate synthetic tutoring dialogs with configurable parameters (topic, difficulty, student type) and output annotated data with move_type, is_correct, emotion, and error_type fields
- **FR-002**: System MUST support QLoRA fine-tuning of the language model on tutoring dialog data with checkpoint saving every epoch
- **FR-003**: System MUST support loading fine-tuned LoRA weights into the production inference server without code changes
- **FR-004**: System MUST train the DKT model on standardized educational datasets and export weights compatible with the existing knowledge tracker
- **FR-005**: System MUST support hybrid knowledge tracing that automatically selects BKT for new users and DKT for users with sufficient history

**ML Components (Month 2)**
- **FR-006**: System MUST classify student emotional state from text messages into 5 categories using a trained language model
- **FR-007**: System MUST support both rule-based and ML-based emotion detection with a configuration switch
- **FR-008**: System MUST recognize mathematical expressions from uploaded images and convert them to machine-readable notation
- **FR-009**: System MUST verify handwritten solution steps against correct answers using a computer algebra system
- **FR-010**: System MUST support controlled experiments with random group assignment, pre/post testing, and statistical analysis

**Evaluation (Month 3)**
- **FR-011**: System MUST compute tutoring quality metrics: Socratic Score, Telling Rate, Error Recovery Rate
- **FR-012**: System MUST compute model comparison metrics: AUC, RMSE, accuracy for knowledge tracing; F1, precision, recall for emotion detection
- **FR-013**: System MUST generate structured comparison reports suitable for academic publication

**Analytics & Export**
- **FR-014**: System MUST display student mastery progression over time as an interactive chart
- **FR-015**: System MUST show an activity heatmap indicating study frequency patterns
- **FR-016**: System MUST display error type distribution and personalized study recommendations
- **FR-017**: System MUST export student progress as a downloadable document with summary, mastery data, errors, and recommendations

**Infrastructure**
- **FR-018**: System MUST cache LLM responses to serve repeated queries without re-generation
- **FR-019**: System MUST pre-compute hints in the background when a new task is assigned
- **FR-020**: System MUST compress conversation context when history exceeds a configurable threshold
- **FR-021**: System MUST persist all sessions and messages to survive server restarts
- **FR-022**: System MUST authenticate users and isolate each user's data
- **FR-023**: System MUST be deployable via a single command using containerization

### Key Entities

- **SyntheticDialog**: Generated tutoring conversation with annotations (topic, difficulty, student_type, turns with move_type/emotion/error_type)
- **TrainingRun**: Record of a model training session (model_type, dataset, hyperparameters, metrics, checkpoint_path)
- **EvaluationReport**: Benchmark results (metric_name, model_a_score, model_b_score, comparison_method, statistical_significance)
- **Experiment**: A/B test configuration (name, groups, allocation, pre_test, post_test, status)
- **ExperimentParticipant**: Student enrolled in experiment (group_assignment, pre_score, post_score, sessions_completed)
- **AnalyticsSnapshot**: Student progress data for dashboard (mastery_by_topic, activity_by_day, error_distribution, recommendations)
- **ExportReport**: Generated progress document (student_id, generation_date, sections, file_path)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Fine-tuned model achieves Socratic Score at least 15 percentage points higher than base model on evaluation dialogs
- **SC-002**: Fine-tuned model Telling Rate is at least 20 percentage points lower than base model
- **SC-003**: DKT model achieves AUC > 0.75 on held-out educational dataset
- **SC-004**: ML emotion detector achieves macro F1 > 0.65, surpassing rule-based baseline by at least 10 percentage points
- **SC-005**: Handwritten solution recognition achieves > 70% formula-level accuracy on test images
- **SC-006**: A/B experiment produces statistically significant results (p < 0.05) on at least one metric
- **SC-007**: Evaluation pipeline generates complete comparison reports within 10 minutes of execution
- **SC-008**: Analytics dashboard loads within 3 seconds with all visualizations rendered
- **SC-009**: LLM cache reduces average response latency by at least 30% for repeated queries
- **SC-010**: All sessions and messages survive server restart with zero data loss
- **SC-011**: System starts from a single deployment command within 5 minutes on a clean machine
- **SC-012**: Two authenticated users cannot access each other's session data

## Assumptions

- Colab Pro+ with A100 GPU is available for all training tasks (fine-tuning, DKT, RuBERT)
- ASSISTments 2009 dataset is publicly available for download
- MathDial or equivalent tutoring dialog dataset is accessible for fine-tuning
- The existing GLM-4.7-Flash model supports LoRA adapter loading via Ollama
- 20-30 students (classmates) are available for the A/B experiment
- CROHME dataset is available for handwritten recognition evaluation
- Local Windows machine has sufficient storage for Docker images and model weights
