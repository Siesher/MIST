# Feature Specification: Next.js UI Migration

**Feature Branch**: `011-nextjs-ui-migration`
**Created**: 2026-02-04
**Status**: Draft
**Input**: Migrate MITS interface from Gradio to FastAPI + Next.js with chat-focused design similar to ChatGPT/Claude

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chat with Math Tutor (Priority: P1) MVP

A student opens the MITS application and starts a tutoring conversation. They type a math question or answer, and the tutor responds in real-time with streaming text. The student sees the tutor's response appear character by character, including properly rendered mathematical formulas.

**Why this priority**: Core tutoring interaction is the primary value proposition. Without working chat, no other features matter.

**Independent Test**: Can be fully tested by opening the app, starting a new session, sending a message, and verifying the tutor responds with properly formatted math. Delivers immediate tutoring value.

**Acceptance Scenarios**:

1. **Given** a student on the chat page, **When** they type a message and press send, **Then** the message appears in the chat and the tutor begins responding within 2 seconds
2. **Given** a tutor response containing math notation (e.g., $x^2$), **When** the response renders, **Then** the mathematical formula displays correctly formatted (not raw LaTeX)
3. **Given** a streaming response in progress, **When** tokens arrive from the server, **Then** the student sees text appearing progressively like a typing animation
4. **Given** the student presses Enter in the input field, **When** text is present, **Then** the message is sent (keyboard shortcut)

---

### User Story 2 - Session Management (Priority: P1)

A student can see their previous tutoring sessions in a sidebar, create new sessions, and switch between them. Each session preserves its conversation history and associated task.

**Why this priority**: Essential for continuity of learning. Students need to resume where they left off.

**Independent Test**: Can be tested by creating multiple sessions, switching between them, and verifying each retains its conversation history.

**Acceptance Scenarios**:

1. **Given** a student with existing sessions, **When** they open the app, **Then** they see a list of their sessions in a sidebar
2. **Given** a student viewing the sidebar, **When** they click "New Chat", **Then** a new empty session is created and becomes active
3. **Given** multiple sessions exist, **When** the student clicks on a different session, **Then** the chat area shows that session's conversation history
4. **Given** a session with a math task, **When** the student returns to it, **Then** the task and all previous messages are preserved

---

### User Story 3 - Task Selection (Priority: P2)

A student can select a math topic and difficulty level to get a practice problem. The system presents an appropriate task and the tutor guides them through solving it using the Socratic method.

**Why this priority**: Structured practice is the secondary learning mode after free-form chat.

**Independent Test**: Can be tested by selecting a topic/difficulty, receiving a task, and verifying the tutor provides appropriate guidance.

**Acceptance Scenarios**:

1. **Given** a student in a chat session, **When** they open the task selector, **Then** they see available topics (derivatives, integrals, limits, etc.) and difficulties (easy, medium, hard)
2. **Given** a topic and difficulty selected, **When** the student confirms, **Then** a new math problem appears in the chat
3. **Given** an active task, **When** the student requests a hint, **Then** the tutor provides a progressive hint without revealing the answer
4. **Given** an active task, **When** the student submits a correct answer, **Then** the system acknowledges success and updates their progress

---

### User Story 4 - Visual Theme Preferences (Priority: P2)

A student can switch between dark and light themes. Their preference persists across sessions.

**Why this priority**: Accessibility and comfort for extended study sessions.

**Independent Test**: Can be tested by toggling theme and verifying the change persists after page reload.

**Acceptance Scenarios**:

1. **Given** the app in dark mode, **When** the student clicks the theme toggle, **Then** the interface switches to light mode
2. **Given** a theme preference set, **When** the student closes and reopens the app, **Then** their theme preference is preserved
3. **Given** any theme, **When** math formulas render, **Then** they are legible against the current background

---

### User Story 5 - Student Progress Dashboard (Priority: P3)

A student can view their learning progress, including mastery levels by topic, recent activity, and session statistics.

**Why this priority**: Motivation and self-awareness support long-term learning but are not required for basic tutoring.

**Independent Test**: Can be tested by viewing the profile page after completing several sessions and verifying accurate statistics.

**Acceptance Scenarios**:

1. **Given** a student with completed sessions, **When** they navigate to the profile page, **Then** they see their mastery level per topic
2. **Given** the profile page, **When** viewing statistics, **Then** the student sees total sessions, success rate, and time spent
3. **Given** skill mastery data, **When** displayed visually, **Then** the student can identify their strongest and weakest areas

---

### User Story 6 - Mobile Responsiveness (Priority: P3)

A student can use the tutoring system effectively on a mobile device with appropriate layout adjustments.

**Why this priority**: Enables studying on the go but desktop is the primary use case.

**Independent Test**: Can be tested by opening the app on a mobile device and completing a tutoring session.

**Acceptance Scenarios**:

1. **Given** a mobile screen width, **When** the app loads, **Then** the sidebar is collapsed by default
2. **Given** a mobile view, **When** the student taps a menu button, **Then** the sidebar slides in as an overlay
3. **Given** any screen size, **When** viewing chat messages, **Then** text and math formulas are readable without horizontal scrolling

---

### Edge Cases

- What happens when network connection is lost during a streaming response?
- How does the system handle very long messages or mathematical expressions?
- What happens when the student submits an empty message?
- How does the system behave when the backend (Ollama) is unavailable?
- What happens when a session has hundreds of messages (performance)?

## Requirements *(mandatory)*

### Functional Requirements

#### Chat Interface
- **FR-001**: System MUST display a chat interface with message bubbles distinguishing student and tutor messages
- **FR-002**: System MUST render mathematical notation in messages using standard LaTeX syntax ($...$ for inline, $$...$$ for block)
- **FR-003**: System MUST support real-time streaming of tutor responses
- **FR-004**: System MUST show a typing indicator while the tutor is generating a response
- **FR-005**: System MUST allow message submission via button click or Enter key

#### Session Management
- **FR-006**: System MUST persist conversation history for each session
- **FR-007**: System MUST display a list of previous sessions in a sidebar
- **FR-008**: System MUST allow creating new sessions
- **FR-009**: System MUST allow switching between sessions without data loss
- **FR-010**: System MUST load session history when a session is selected

#### Task Selection
- **FR-011**: System MUST provide a topic selection interface (derivatives, integrals, limits, etc.)
- **FR-012**: System MUST provide difficulty selection (easy, medium, hard, olympiad)
- **FR-013**: System MUST fetch and display tasks from the existing task bank
- **FR-014**: System MUST support hint requests during task solving

#### Theme & Preferences
- **FR-015**: System MUST support dark and light color themes
- **FR-016**: System MUST persist theme preference in browser storage
- **FR-017**: System MUST apply saved theme on application load

#### Student Profile
- **FR-018**: System MUST display student's topic mastery levels
- **FR-019**: System MUST show session statistics (total, success rate, time)
- **FR-020**: System MUST visualize skill progress over time

#### Responsiveness
- **FR-021**: System MUST adapt layout for mobile, tablet, and desktop screens
- **FR-022**: System MUST provide a collapsible sidebar for mobile views
- **FR-023**: System MUST ensure all interactive elements are touch-friendly on mobile

#### Integration
- **FR-024**: System MUST communicate with backend via REST API for non-streaming operations
- **FR-025**: System MUST use WebSocket for real-time streaming responses
- **FR-026**: System MUST handle backend unavailability gracefully with user-friendly error messages
- **FR-027**: System MUST maintain compatibility with existing MITS core logic (agents, RAG, memory)

### Key Entities

- **Session**: A tutoring conversation with unique ID, creation timestamp, associated task (optional), conversation history, and status (active/completed)
- **Message**: An individual chat turn with role (student/tutor), content, timestamp, and optional metadata (move type, thinking process)
- **Task**: A math problem with topic, difficulty, problem text, hints, solution, and answer
- **StudentProfile**: Aggregated learning data with mastery scores by topic, session history reference, and preferences

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Students can send a message and see the tutor's first response token within 3 seconds
- **SC-002**: Mathematical formulas render correctly in 100% of messages containing LaTeX notation
- **SC-003**: Students can complete a full tutoring session (5+ exchanges) on mobile devices without usability issues
- **SC-004**: Session switching preserves full conversation history with zero data loss
- **SC-005**: The interface loads and becomes interactive within 2 seconds on standard connections
- **SC-006**: Theme preference persists across 100% of browser sessions
- **SC-007**: The interface presents a professional, modern appearance suitable for diploma defense presentation

## Assumptions

- Students use modern web browsers (Chrome, Firefox, Safari, Edge - latest 2 versions)
- Backend services (FastAPI, Ollama) run on the same machine or local network
- Existing MITS core logic (agents, RAG, memory, knowledge tracking) remains unchanged
- Session data storage uses existing SQLite database schema
- Students have stable internet connection for initial load (offline mode handled by existing Feature 010)

## Out of Scope

- User registration and authentication (single-user diploma demo)
- Multi-language interface (Russian only, matching existing system)
- Code execution for programming tasks (focus on math tutoring first)
- Real-time collaboration between multiple students
- Native mobile applications (web-only)
