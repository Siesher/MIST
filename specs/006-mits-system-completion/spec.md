# Feature Specification: MITS System Completion

**Feature Branch**: `006-mits-system-completion`
**Created**: 2026-02-02
**Status**: Draft
**Input**: Complete MITS (Math Intelligent Tutoring System) based on 2025-2026 research in ITS, Knowledge Tracing, RAG, and Socratic tutoring methods.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Adaptive Socratic Tutoring Session (Priority: P1)

A student starts a math tutoring session. Instead of receiving direct answers, the system engages them through Socratic questioning, guiding them to discover solutions themselves. The tutor adapts question difficulty based on the student's demonstrated knowledge level.

**Why this priority**: Core value proposition - the Socratic method is the primary pedagogical approach that differentiates MITS from simple Q&A systems.

**Independent Test**: Student can complete a full tutoring session on any math topic, receiving guided questions rather than direct answers, with the system tracking their progress.

**Acceptance Scenarios**:

1. **Given** a student asks for help with a quadratic equation, **When** they request "solve x²-5x+6=0", **Then** the tutor responds with guiding questions like "What values would multiply to give 6?" instead of the answer.
2. **Given** a student provides an incorrect intermediate step, **When** the system detects the error, **Then** it asks clarifying questions to help the student identify their mistake.
3. **Given** a student is struggling after 3 hints, **When** frustration is detected, **Then** the system provides more direct scaffolding while still maintaining Socratic approach.

---

### User Story 2 - Knowledge State Tracking (Priority: P1)

The system continuously tracks student knowledge across multiple math topics (algebra, calculus, geometry, etc.) and uses this information to personalize task selection and hint delivery.

**Why this priority**: Knowledge tracing enables all adaptive features - without it, the system cannot personalize the learning experience.

**Independent Test**: A student's knowledge state is updated after each interaction and influences the next task/hint selection.

**Acceptance Scenarios**:

1. **Given** a student correctly solves 3 consecutive algebra problems, **When** requesting a new task, **Then** the system increases difficulty for algebra topics.
2. **Given** a student struggles with derivatives, **When** viewing their profile, **Then** the system shows a lower mastery level for calculus concepts.
3. **Given** a new student with no history, **When** they start their first session, **Then** the system uses Bayesian Knowledge Tracing defaults and calibrates quickly based on initial responses.

---

### User Story 3 - RAG-Enhanced Hint Delivery (Priority: P2)

When providing hints, the system retrieves relevant explanations, common misconceptions, and worked examples from a curated knowledge base, ensuring accurate and contextual support.

**Why this priority**: RAG eliminates hallucinations in educational content and provides consistent, curriculum-aligned hints.

**Independent Test**: Hints retrieved from the knowledge base are relevant to the current problem and student's specific misconception.

**Acceptance Scenarios**:

1. **Given** a student makes a common sign error in algebra, **When** the system generates a hint, **Then** it retrieves the specific misconception from the knowledge base and addresses it directly.
2. **Given** a complex calculus problem, **When** the student requests an example, **Then** the system retrieves a similar worked example from the knowledge base.
3. **Given** a student working on a problem, **When** RAG finds no relevant content, **Then** the system falls back to LLM-generated hints with appropriate disclaimers.

---

### User Story 4 - Cognitive Load Management (Priority: P2)

The system monitors student cognitive load during sessions and adjusts the complexity of problems, hints, and explanations accordingly to maintain optimal challenge level.

**Why this priority**: Prevents student frustration and cognitive overload while ensuring continuous learning progress.

**Independent Test**: When cognitive load indicators suggest overload, the system automatically simplifies the next interaction.

**Acceptance Scenarios**:

1. **Given** a student takes significantly longer than usual to respond, **When** submitting their next answer, **Then** the system offers a simpler follow-up task.
2. **Given** a student makes multiple errors in quick succession, **When** error pattern is detected, **Then** the system suggests a break or provides easier practice problems.
3. **Given** a student is performing well, **When** cognitive load is low, **Then** the system gradually increases problem complexity.

---

### User Story 5 - Multi-Agent Orchestration (Priority: P2)

Multiple specialized agents (Tutor, Profiler, Planner, Verifier, TaskGenerator) work together to provide a coherent learning experience, each handling their specific responsibility.

**Why this priority**: Clean separation of concerns enables better maintainability and allows each agent to be optimized independently.

**Independent Test**: Each agent performs its designated function and agents communicate correctly to produce coherent tutoring behavior.

**Acceptance Scenarios**:

1. **Given** a tutoring session starts, **When** the orchestrator receives a student query, **Then** it routes to appropriate agents (Profiler for assessment, Tutor for response).
2. **Given** a student completes a task, **When** verification is needed, **Then** the Verifier agent checks the solution and passes feedback to the Tutor.
3. **Given** a student needs a new practice problem, **When** requested, **Then** TaskGenerator creates an appropriate problem based on Profiler's knowledge state data.

---

### User Story 6 - Dual-Memory Personalization (Priority: P3)

The system maintains both short-term (session) and long-term (persistent) memory to provide personalized experience across sessions while maintaining context within a session.

**Why this priority**: Enables continuity across learning sessions and deep personalization over time.

**Independent Test**: Student returns after days/weeks and system remembers their progress, preferences, and knowledge state.

**Acceptance Scenarios**:

1. **Given** a student returns after 1 week, **When** they start a new session, **Then** the system recalls their previous topics, mastery levels, and preferences.
2. **Given** a student mentions preferring visual explanations, **When** noted in session, **Then** this preference persists to future sessions.
3. **Given** within a single session, **When** student references "that problem from earlier", **Then** system uses session memory to understand the reference.

---

### User Story 7 - Russian Language Support (Priority: P3)

The system fully supports Russian language for all interactions, including mathematical terminology, hints, and Socratic questioning.

**Why this priority**: Required for target user base; ensures accessibility for Russian-speaking students.

**Independent Test**: Complete tutoring session can be conducted entirely in Russian with proper mathematical terminology.

**Acceptance Scenarios**:

1. **Given** a student writes in Russian, **When** asking about "квадратное уравнение", **Then** the system responds in Russian with correct mathematical terms.
2. **Given** Russian mathematical notation conventions, **When** displaying formulas, **Then** the system uses appropriate notation (e.g., "tg" instead of "tan").
3. **Given** a mixed Russian/English input, **When** processing, **Then** the system responds in the dominant language of the input.

---

### Edge Cases

- What happens when student provides empty or gibberish input?
- How does system handle mathematical notation errors (malformed LaTeX)?
- What happens when Ollama service is unavailable?
- How does system handle extremely long response times from LLM?
- What happens when student knowledge state has conflicting signals?
- How does system handle session timeout during active tutoring?

## Requirements *(mandatory)*

### Functional Requirements

#### Knowledge Tracing
- **FR-001**: System MUST track student knowledge state across defined math topics (algebra, calculus, geometry, trigonometry, linear algebra, probability)
- **FR-002**: System MUST use Bayesian Knowledge Tracing (BKT) for new students with limited interaction history (<10 responses)
- **FR-003**: System MUST transition to Deep Knowledge Tracing (DKT) model after sufficient interaction history (≥10 responses)
- **FR-004**: System MUST estimate cognitive load based on response time, error patterns, and interaction frequency
- **FR-005**: System MUST adjust task difficulty based on current knowledge state and cognitive load

#### RAG System
- **FR-006**: System MUST maintain a vector knowledge base of math concepts, hints, misconceptions, and worked examples
- **FR-007**: System MUST retrieve relevant content based on current problem context and student's specific error pattern
- **FR-008**: System MUST re-rank retrieved content based on student's knowledge state and cognitive load
- **FR-009**: System MUST provide fallback to LLM generation when no relevant content is found in knowledge base
- **FR-010**: System MUST support indexing of mathematical formulas and notation

#### Socratic Tutoring
- **FR-011**: System MUST respond with guiding questions rather than direct answers (unless student explicitly requests solution)
- **FR-012**: System MUST detect when student is struggling and provide progressive scaffolding
- **FR-013**: System MUST maintain Socratic dialogue flow across multiple conversation turns
- **FR-014**: System MUST provide metacognitive prompts to encourage self-reflection

#### Multi-Agent Architecture
- **FR-015**: System MUST have distinct agents for: Tutoring, Profiling, Planning, Verification, Task Generation, and Orchestration
- **FR-016**: Orchestrator agent MUST route requests to appropriate specialized agents
- **FR-017**: Agents MUST communicate through defined interfaces without tight coupling
- **FR-018**: System MUST support graceful degradation when individual agents fail

#### Memory & Personalization
- **FR-019**: System MUST maintain session memory (current conversation context, referenced problems)
- **FR-020**: System MUST persist long-term memory (knowledge state, preferences, history) across sessions
- **FR-021**: System MUST allow students to view and modify their stored preferences
- **FR-022**: System MUST apply knowledge decay model for topics not practiced recently

#### Language Support
- **FR-023**: System MUST support Russian language for all user-facing interactions
- **FR-024**: System MUST use appropriate Russian mathematical terminology and notation
- **FR-025**: System MUST detect input language and respond in the same language

### Key Entities

- **Student**: Represents a learner with unique profile, knowledge state, preferences, and interaction history
- **KnowledgeState**: Tracks mastery level (0-1) for each topic, last practice date, and learning velocity
- **Topic**: Mathematical concept with prerequisites, difficulty level, and associated misconceptions
- **Task**: Math problem with difficulty, topic tags, solution steps, and common errors
- **Session**: Single tutoring interaction with conversation history, start/end time, and performance metrics
- **Hint**: Educational content piece with topic association, difficulty level, and retrieval embeddings
- **Misconception**: Common error pattern with detection rules, correction hints, and topic links

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Students report improved understanding in 80% of tutoring sessions (post-session survey)
- **SC-002**: System maintains Socratic dialogue (guiding questions vs direct answers) in 90% of interactions
- **SC-003**: Knowledge state predictions align with actual student performance with 75% accuracy
- **SC-004**: RAG-retrieved hints are rated as relevant by students in 85% of cases
- **SC-005**: System adapts task difficulty appropriately in 80% of difficulty adjustment decisions
- **SC-006**: Students can complete typical tutoring sessions within 15-30 minutes
- **SC-007**: System handles 50 concurrent student sessions without performance degradation
- **SC-008**: Russian language interactions have equivalent quality to English interactions
- **SC-009**: Session continuity preserved for returning students in 95% of cases
- **SC-010**: Average hint delivery time under 5 seconds including RAG retrieval

## Assumptions

1. GLM-4.7-Flash (19GB) model provides sufficient quality for Socratic tutoring in mathematics
2. Ollama service is available and properly configured on the target deployment environment
3. ChromaDB provides adequate performance for the expected knowledge base size (<100K documents)
4. Students have basic familiarity with mathematical notation
5. Initial knowledge base will be seeded with algebra, calculus, and basic geometry content
6. Session length averaging 20-30 minutes is acceptable for target users
7. BKT model parameters will be tuned based on standard educational research values

## Out of Scope

1. Voice/audio input and output
2. Handwriting recognition for mathematical notation
3. Real-time collaborative tutoring (multiple students)
4. Integration with external LMS (Learning Management Systems)
5. Mobile-specific optimizations
6. Offline functionality
7. Assessment certification or grading
8. Parent/teacher dashboard (future feature)
