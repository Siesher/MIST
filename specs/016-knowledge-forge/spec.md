# Feature Specification: Knowledge Forge — Personalized Knowledge Graph Navigator

**Feature Branch**: `016-knowledge-forge`  
**Created**: 2026-04-16  
**Status**: Draft  
**Input**: Replace passive RAG with an active Knowledge Forge system where the tutor LLM navigates a structured knowledge graph personalized to each student's BKT mastery state.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tutor Navigates Knowledge Graph During Session (Priority: P1)

During a tutoring session, the LLM tutor actively queries the knowledge graph to retrieve precise, structured information about the topic being discussed — formulas, prerequisites, worked examples, and common misconceptions — personalized to what the student already knows.

**Why this priority**: This is the core value proposition. Without tutor-side graph navigation, the system is just a static knowledge store. The tutor must be able to use tools to explore concepts, check student prerequisites, and adapt explanations in real time.

**Independent Test**: Start a tutoring session on "definite integrals" with a student who has mastered limits but not antiderivatives. The tutor should (via tool calls) discover the prerequisite gap and adjust its teaching approach accordingly.

**Acceptance Scenarios**:

1. **Given** a student asks about definite integrals, **When** the tutor invokes the `explore_concept` tool, **Then** it receives the concept definition, related formulas, applicable methods, and the student's mastery of each prerequisite.
2. **Given** a student has a gap in antiderivatives (mastery < 0.4), **When** the tutor invokes `diagnose_gap` for definite integrals, **Then** it receives "antiderivatives" as the root gap with a suggested review path.
3. **Given** the tutor needs to decide what to teach next, **When** it invokes `suggest_next`, **Then** it receives the concept with the highest readiness score from the student's learning frontier.

---

### User Story 2 - Knowledge Graph Seeded from Existing Data (Priority: P1)

The existing skill graph (40+ skills with prerequisites) and SKI knowledge cards (textbook entries with formulas, examples, methods) are migrated into the Knowledge Forge graph format, creating a usable knowledge base from day one.

**Why this priority**: Without seed data, the graph is empty and the navigator has nothing to work with. This is a prerequisite for all other stories.

**Independent Test**: Run the migration script, load the resulting `forge.json`, and verify that all skills from `skill_graph.json` appear as CONCEPT nodes with correct PREREQUISITE edges, and all SKI cards are represented as linked nodes.

**Acceptance Scenarios**:

1. **Given** the existing `skill_graph.json` with 40+ skills, **When** the migration runs, **Then** each skill becomes a CONCEPT node with its Russian name, difficulty, and category preserved.
2. **Given** skills with prerequisites in the skill graph, **When** the migration runs, **Then** corresponding PREREQUISITE edges are created between concept nodes.
3. **Given** SKI knowledge cards (e.g., quadratic equations), **When** the migration runs, **Then** formulas become FORMULA nodes, worked examples become EXAMPLE nodes, common errors become MISCONCEPTION nodes, all linked to the parent concept via appropriate edges.

---

### User Story 3 - Personalized Learning Path Computation (Priority: P2)

Given a target concept the student wants to learn, the system computes the optimal learning path from the student's current knowledge, accounting for mastery levels and concept difficulty.

**Why this priority**: Learning paths are a key differentiator from static tutoring. They provide the "GPS navigation" experience for education. However, the system is functional without them (tutor can still explore concepts and diagnose gaps).

**Independent Test**: Create a student with mastery in basic algebra but not calculus. Request a path to "integration by parts." Verify the path traverses through limits, derivatives, and antiderivatives in a logical order, skipping already-mastered concepts.

**Acceptance Scenarios**:

1. **Given** a student who has mastered algebra and functions, **When** the system computes a path to "definite integrals", **Then** the path includes only unmastered prerequisites in dependency order.
2. **Given** two possible routes to a concept, **When** the system computes the optimal path, **Then** it selects the path with lower total cost (balancing difficulty and existing mastery).
3. **Given** a student has already mastered the target concept, **When** a path is requested, **Then** the system returns an empty path with zero cost.

---

### User Story 4 - Planner Uses Graph for Strategy Selection (Priority: P2)

The teaching strategy planner uses graph navigation (prerequisite gaps, misconception links, learning frontier) alongside its existing rule-based logic to make better-informed pedagogical decisions.

**Why this priority**: This connects the knowledge graph to actual tutoring behavior. Without this integration, the graph exists in isolation. The planner already has a working rule-based system, so this enhances rather than replaces it.

**Independent Test**: Simulate a student who fails at the chain rule. Verify the planner receives gap diagnosis (missing product rule), related misconceptions, and adjusts strategy to include prerequisite review.

**Acceptance Scenarios**:

1. **Given** a student error diagnosed on a concept with prerequisite gaps, **When** the planner selects a strategy, **Then** it includes prerequisite review in the teaching plan.
2. **Given** the knowledge graph links a misconception to the current concept, **When** the planner selects a strategy, **Then** it factors in the misconception for repair moves.
3. **Given** the graph navigator is unavailable (degraded mode), **When** the planner selects a strategy, **Then** it falls back to existing rule-based logic without errors.

---

### User Story 5 - Source Document Extraction (Priority: P3)

A teacher or administrator provides a source document (textbook chapter, article) and the system uses an LLM agent to extract structured knowledge — concepts, formulas, theorems, examples, and their relationships — adding them to the knowledge graph.

**Why this priority**: This enables the graph to grow beyond the initial seed data. However, the system is fully functional with just the seed data, making this an enhancement.

**Independent Test**: Provide a short textbook section on "limits" (2-3 paragraphs with definitions and examples). Verify the extractor creates appropriate CONCEPT, FORMULA, and EXAMPLE nodes with correct relationships.

**Acceptance Scenarios**:

1. **Given** a textbook section containing a definition, **When** the extractor processes it, **Then** a CONCEPT node is created with the definition as content.
2. **Given** a textbook section with a formula and example, **When** the extractor processes it, **Then** FORMULA and EXAMPLE nodes are created and linked to the concept via appropriate edges.
3. **Given** an extracted concept that already exists in the graph, **When** the extractor encounters it, **Then** it enriches the existing node rather than creating a duplicate.

---

### Edge Cases

- What happens when a concept has no prerequisites in the graph? (Entry-point concept — always available on the frontier with readiness based on own mastery and difficulty)
- What happens when the student has no mastery data at all? (Cold start — frontier returns entry-point concepts sorted by difficulty ascending)
- What happens when there's no path between two concepts in the graph? (Disconnected subgraphs — return None, let the tutor handle gracefully)
- What happens when the source extractor produces low-confidence nodes? (Store with confidence < 1.0, flag for human review, exclude from tool results until verified)
- What happens when two extracted concepts are duplicates? (Fuzzy matching on title + domain; merge if high similarity, flag if ambiguous)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain a persistent knowledge graph of STEM concepts, formulas, theorems, examples, methods, and misconceptions connected by typed directed edges.
- **FR-002**: System MUST overlay student mastery data (from BKT) onto the knowledge graph to compute personalized learning frontiers (ZPD on graph).
- **FR-003**: System MUST provide tool-callable functions that the tutor LLM can invoke during sessions to navigate the graph (explore concept, diagnose gap, find path, suggest next, get concept context).
- **FR-004**: System MUST compute optimal learning paths from current student knowledge to any target concept using mastery-weighted graph traversal.
- **FR-005**: System MUST diagnose prerequisite gaps when a student fails at a concept by traversing prerequisite edges backward to find unmastered fundamentals.
- **FR-006**: System MUST migrate existing skill graph (40+ skills) and SKI knowledge cards into the Knowledge Forge graph format as seed data.
- **FR-007**: System MUST persist the knowledge graph as a JSON file that loads at startup and saves on modification.
- **FR-008**: System MUST extract structured knowledge from source documents using LLM-based analysis, producing nodes and edges for graph ingestion.
- **FR-009**: System MUST integrate graph navigation results into the planner agent's strategy selection, providing prerequisite gaps and misconception data.
- **FR-010**: System MUST gracefully degrade when the knowledge graph is empty or the navigator is unavailable, falling back to existing rule-based behavior.
- **FR-011**: System MUST score frontier concepts by combining prerequisite readiness, own mastery, and concept difficulty to produce a readiness ranking.
- **FR-012**: System MUST provide rich concept context to the tutor including the student's mastery of prerequisites, related misconceptions, applicable methods, and illustrating examples.

### Key Entities

- **KnowledgeNode**: A unit of knowledge (concept, formula, theorem, example, method, or misconception) with title, content, domain, difficulty, tags, source attribution, and extraction confidence.
- **KnowledgeEdge**: A directed relationship between two nodes (10 types: prerequisite, part_of, generalizes, confused_with, common_error_for, applies_to, derived_from, proves, best_taught_after, illustrates) with optional weight.
- **KnowledgeGraph**: The full graph structure with nodes, edges, adjacency indexes, and domain/type indexes. Supports CRUD, navigation, and persistence.
- **PersonalizedNavigator**: The bridge that combines a KnowledgeGraph with a student's mastery state to provide learning frontiers, gap diagnosis, optimal paths, and concept context.
- **FrontierNode**: A concept at the edge of the student's knowledge zone — prerequisites mostly mastered but the concept itself not yet learned. Scored by readiness.
- **GapDiagnosis**: Analysis of why a student failed — lists missing prerequisites, root cause, suggested review path, and related misconceptions.
- **LearningPath**: An ordered sequence of concepts from current knowledge to a target, with mastery values and estimated new concepts to learn.
- **SourceExtractor**: An LLM agent that reads documents and produces KnowledgeNodes and KnowledgeEdges for graph ingestion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tutor can invoke graph navigation tools and receive structured responses within a single tutoring turn (graph queries complete within 100ms for a graph of 200+ nodes).
- **SC-002**: Learning frontier correctly identifies concepts where 80%+ of prerequisites are mastered but the concept itself is below mastery threshold — verified on 5+ student profiles with known mastery distributions.
- **SC-003**: Gap diagnosis correctly identifies the root missing prerequisite in 90%+ of test cases with known prerequisite chains.
- **SC-004**: Optimal path computation returns valid dependency-ordered paths — no concept appears before its prerequisites in the path.
- **SC-005**: Seed migration preserves all 40+ skills from existing skill graph as concept nodes with correct prerequisite edges, verified by automated comparison.
- **SC-006**: Source extractor produces nodes with correct types and meaningful relationships for 80%+ of concepts in a test document, as judged by manual review.
- **SC-007**: Planner produces improved strategy selections when graph data is available versus without — measurable on 10+ diagnostic scenarios.
- **SC-008**: System operates correctly when the graph is empty or unavailable, with no errors and graceful fallback to existing behavior.
