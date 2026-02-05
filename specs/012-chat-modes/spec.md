# Feature Specification: Universal Chat Modes

**Feature Branch**: `012-chat-modes`
**Created**: 2026-02-05
**Status**: Draft
**Input**: Universal chat interface with three operating modes: Chat, Guided Learning, Task Generator

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Switch Between Chat Modes (Priority: P1)

A user opens MITS and wants to have a casual conversation about programming concepts. They select "Обычный чат" mode from the dropdown menu and engage in free-form dialogue. Later, they want to practice calculus, so they switch to "Guided Learning" mode and receive Socratic-style tutoring.

**Why this priority**: Mode switching is the core feature that enables all other functionality. Without it, the system remains single-purpose.

**Independent Test**: Can be fully tested by selecting different modes from dropdown and verifying the model's response style changes accordingly.

**Acceptance Scenarios**:

1. **Given** user is in any chat session, **When** they click the mode selector dropdown, **Then** they see three options: "Обычный чат", "Guided Learning", "Генерация задач"
2. **Given** user selects a different mode, **When** mode changes, **Then** visual indicator updates (icon and color) and next message uses new mode's behavior
3. **Given** user switches modes mid-conversation, **When** mode changes, **Then** chat history remains visible and preserved

---

### User Story 2 - Free Chat Mode (Priority: P1)

A user wants to discuss neural networks, ask about Python syntax, or have a general conversation. They select "Обычный чат" mode and the assistant responds helpfully without pedagogical constraints.

**Why this priority**: Expands system utility beyond math tutoring, making it a general-purpose assistant.

**Independent Test**: Can be tested by asking off-topic questions (e.g., "How do neural networks work?") and verifying the assistant provides direct, helpful answers.

**Acceptance Scenarios**:

1. **Given** user is in Chat mode, **When** they ask any question, **Then** assistant responds directly and helpfully without Socratic questioning
2. **Given** user is in Chat mode, **When** they ask about programming, **Then** assistant can provide code examples and explanations
3. **Given** user is in Chat mode, **When** they ask about non-math topics, **Then** assistant engages naturally without redirecting to math

---

### User Story 3 - Guided Learning Mode (Priority: P1)

A student wants to learn derivatives through guided discovery. They select "Guided Learning" mode, and the tutor asks probing questions, provides hints when requested, and helps them arrive at solutions independently.

**Why this priority**: Core tutoring functionality that already exists - must be preserved and integrated.

**Independent Test**: Can be tested by presenting a math problem and verifying the tutor asks guiding questions rather than giving direct answers.

**Acceptance Scenarios**:

1. **Given** user is in Guided Learning mode, **When** they ask for help with a math problem, **Then** tutor responds with guiding questions
2. **Given** user is in Guided Learning mode, **When** they request a hint, **Then** tutor provides incremental hints (up to configured limit)
3. **Given** user gives an incorrect answer, **When** tutor responds, **Then** tutor asks clarifying questions to help identify the error

---

### User Story 4 - Task Generation Mode (Priority: P2)

A student wants practice problems on integrals at intermediate difficulty. They select "Генерация задач" mode, specify the topic and difficulty, and receive generated problems with solutions available on demand.

**Why this priority**: Extends learning capabilities but depends on core mode switching being functional first.

**Independent Test**: Can be tested by requesting "Generate 3 problems about derivatives, medium difficulty" and verifying appropriate problems are created.

**Acceptance Scenarios**:

1. **Given** user is in Task Generation mode, **When** they request problems on a topic, **Then** system generates appropriate math problems
2. **Given** user requests problems with specific difficulty, **When** problems are generated, **Then** difficulty matches request (easy/medium/hard)
3. **Given** problems are generated, **When** user requests solution, **Then** step-by-step solution is revealed

---

### Edge Cases

- What happens when user switches mode while assistant is streaming a response? Response is cancelled, mode switches immediately
- How does system handle mode switch with empty chat history? Switch immediately, no confirmation needed
- What happens if user asks math question in Chat mode? Answer directly, don't force Guided Learning mode
- How does system handle invalid/unsupported topic in Task Generation? Inform user, suggest available topics
- What if user sends empty message after mode switch? Show appropriate placeholder text for current mode

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a mode selector dropdown in the chat input area
- **FR-002**: System MUST support three distinct modes: Chat, Guided Learning, Task Generator
- **FR-003**: System MUST visually indicate current mode with icon and color coding
- **FR-004**: System MUST preserve chat history when switching between modes
- **FR-005**: System MUST use mode-specific system prompts for each mode
- **FR-006**: System MUST store current mode as part of session state
- **FR-007**: Chat mode MUST allow free-form conversation on any topic
- **FR-008**: Guided Learning mode MUST use Socratic method (questions, not answers)
- **FR-009**: Task Generator mode MUST accept topic and difficulty parameters
- **FR-010**: Task Generator mode MUST generate problems with available solutions
- **FR-011**: System MUST provide backend endpoint to change session mode
- **FR-012**: Mode change MUST take effect on the next user message
- **FR-013**: System MUST display mode-specific placeholder text in input field

### Key Entities

- **ChatMode**: Enumeration of available modes (chat, guided_learning, task_generator) with associated display names, icons, and colors
- **Session**: Extended to include current_mode field tracking active mode
- **ModeConfig**: Configuration for each mode including system prompt template and behavior flags

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can switch between all three modes within 2 clicks (dropdown + selection)
- **SC-002**: Mode indicator is visible at all times during chat session
- **SC-003**: Chat mode provides direct answers to 95% of general questions without redirecting
- **SC-004**: Guided Learning mode asks at least one guiding question before providing hints
- **SC-005**: Task Generator produces valid, solvable problems for requested topic 90% of time
- **SC-006**: Mode switching completes in under 500ms with no visible page reload
- **SC-007**: Chat history remains intact across mode switches (0% message loss)

## Assumptions

- Default mode for new sessions is "Guided Learning" to maintain backward compatibility
- Mode-specific system prompts are stored in configuration, not hardcoded
- All three modes use the same underlying LLM, only prompts differ
- Task generation reuses existing task bank and generation logic from current implementation
- Russian language is the primary UI language for mode names and indicators
