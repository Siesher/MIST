# Research: Knowledge Forge

**Feature**: 016-knowledge-forge | **Date**: 2026-04-16

## R1: Graph Navigation vs RAG for Tutoring

**Decision**: Replace passive RAG with tool-based graph navigation.

**Rationale**: STEM knowledge is inherently structured (prerequisites, theorems, proofs). RAG treats knowledge as flat text chunks and relies on embedding similarity, which cannot:
- Traverse prerequisite chains (algebra → calculus)
- Overlay student mastery state on knowledge structure
- Compute learning frontiers (ZPD on graph)
- Diagnose root-cause prerequisite gaps

The knowledge graph preserves these relationships natively. The tutor LLM navigates it via tool calling (already supported by Ollama + existing `chat_with_tools()`).

**Alternatives considered**:
- **GraphRAG (Microsoft)**: Builds community summaries from text. Designed for open-domain QA, not tutoring with student models. Overkill for 200 structured concepts.
- **Hybrid RAG + Graph**: Use RAG for free-text questions, graph for structured navigation. Rejected for MVP — adds complexity without clear benefit. Can be added later.
- **Pure embedding search on graph nodes**: Loses structural relationships. Cosine similarity between "derivative" and "integral" is high, but they have a clear prerequisite ordering.

## R2: Graph Persistence Format

**Decision**: Single JSON file (`data/knowledge/forge.json`).

**Rationale**: 
- 200 nodes + ~500 edges ≈ 100-200 KB JSON. No performance concern.
- Load once at startup, save on modification. No database overhead.
- Human-readable, git-diffable, easy to review.
- Existing project uses JSON for skill_graph.json and all knowledge files.

**Alternatives considered**:
- **SQLite**: Overkill for 200 nodes. Adds query complexity without benefit at this scale.
- **Neo4j/ArangoDB**: External dependency, deployment complexity. Violates "no external graph DB" constraint.
- **NetworkX + pickle**: NetworkX adds dependency; pickle isn't human-readable or git-diffable.

## R3: Tool Calling Pattern for Navigator

**Decision**: Extend existing SKI tool pattern — add navigator tools alongside, not replacing.

**Rationale**: 
- `tutor_agent.py` already injects `SKI_TOOL_DEFINITIONS` + `SKI_FUNCTIONS` via `llm.chat_with_tools()`.
- Navigator tools follow the exact same Ollama format: `[{"type": "function", "function": {...}}]`.
- Tutor gets both SKI tools (backward compat) and navigator tools (new graph features).
- `max_tool_rounds=3` already supports multi-step navigation (explore → diagnose → suggest).

**Integration point**: `tutor_agent.py` lines 494-500. Merge tool lists:
```python
all_tools = self._ski_tool_defs + self._navigator_tool_defs
all_functions = {**self._ski_functions, **self._navigator_functions}
result = self.llm.chat_with_tools(tools=all_tools, available_functions=all_functions, ...)
```

## R4: Planner Integration Strategy

**Decision**: Extend `create_plan()` input with optional graph context; keep rule-based logic as primary, graph as enrichment.

**Rationale**:
- Planner's `create_plan(profile, context, available_hints)` already accepts student profile with `mastery_by_skill`.
- Add optional `graph_context: Optional[Dict]` parameter with gap diagnosis and frontier data.
- Rule-based strategy selection (13 rules) remains primary. Graph data enriches:
  - `prerequisites_to_review` field populated from `diagnose_gap()` results
  - Strategy selection considers whether gaps are prerequisite-level (→ REVIEW) or misconception-level (→ CONCEPTUAL_REPAIR)
- Graceful degradation: if graph unavailable, `graph_context=None`, existing logic unchanged.

**Integration point**: `planner.py` line 238 — add parameter. `orchestrator.py` line 944 — pass graph results to planner.

## R5: Readiness Scoring Function Design

**Decision**: Weighted composite score combining prerequisite completeness, mastery quality, own mastery, and difficulty alignment.

**Rationale**: The readiness score must balance:
1. **Prerequisite gate**: If critical prereqs are missing, score should be near zero regardless of other factors. A single gap in foundation can block understanding.
2. **Mastery quality**: Having prereqs at 0.71 (barely passed) vs 0.95 (solid) matters.
3. **Own mastery**: Low own mastery = high learning potential. Already at 0.6 = less frontier value.
4. **Difficulty**: Hard concepts need stronger prerequisites.

Formula approach:
- Gate: `min_prereq_ratio = n_mastered / n_total` — must be > 0.5 to be considered
- Quality: `prereq_mastery_avg` weighted into score
- Novelty: `(1 - own_mastery)` as multiplicative factor
- Difficulty: penalize high difficulty when prereq quality is moderate

## R6: Source Extractor Architecture

**Decision**: LLM agent with structured output (JSON mode) that processes text and returns nodes + edges.

**Rationale**:
- Use Ollama's JSON mode (`format: "json"`) to get structured extraction.
- Two-pass extraction: (1) identify concepts/entities, (2) identify relationships.
- Each extracted node gets `confidence < 1.0` to distinguish from manually verified data.
- Existing `chat_with_tools()` supports multi-round extraction if needed.

**Alternatives considered**:
- **spaCy NER + dependency parsing**: Language-dependent, weak on mathematical notation, doesn't understand STEM semantics.
- **REBEL/DeepKE trained extractors**: Requires fine-tuning for STEM domain. Too heavy for MVP.
- **Manual extraction only**: Doesn't scale. LLM extraction is the pragmatic middle ground.

## R7: Migration Strategy for Existing Data

**Decision**: One-time migration script that converts skill_graph.json → CONCEPT nodes + PREREQUISITE edges, and SKI cards → FORMULA/EXAMPLE/METHOD/MISCONCEPTION nodes linked to parent concepts.

**Rationale**:
- `skill_graph.json` has 40+ skills with `prerequisites`, `difficulty`, `category`, `name_ru` — maps directly to CONCEPT nodes + PREREQUISITE edges.
- SKI `KnowledgeCard` has 16 fields that decompose into:
  - Card itself → CONCEPT node (definition, domain, difficulty)
  - `key_formulas` → FORMULA nodes + DERIVED_FROM edges
  - `worked_examples` → EXAMPLE nodes + ILLUSTRATES edges
  - `solution_methods` → METHOD nodes + APPLIES_TO edges
  - `common_errors` → MISCONCEPTION nodes + COMMON_ERROR_FOR edges
  - `prerequisites` → PREREQUISITE edges
- Migration is idempotent: can be re-run without duplicates (check by ID).
- Output: `data/knowledge/forge.json` with seed graph.
