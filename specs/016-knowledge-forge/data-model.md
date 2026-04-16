# Data Model: Knowledge Forge

**Feature**: 016-knowledge-forge | **Date**: 2026-04-16

## Entities

### KnowledgeNode

A unit of knowledge in the graph.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | yes | Unique ID, format: `{domain}:{topic}:{subtype}` (e.g. `math:derivative:definition`) |
| node_type | enum | yes | CONCEPT, FORMULA, THEOREM, EXAMPLE, METHOD, MISCONCEPTION |
| title | string | yes | Human-readable title (Russian) |
| title_en | string | yes | English title (for code/search) |
| content | string | yes | Main content: definition, formula text, steps, etc. |
| domain | string | yes | Subject domain: math, physics, chemistry, biology, cs |
| tags | list[string] | no | Searchable tags |
| difficulty | float | no | 0.0 (trivial) to 1.0 (olympiad). Default: 0.5 |
| source | string | no | Where extracted from (document name, URL) |
| metadata | dict | no | Type-specific data (e.g. LaTeX for formulas, steps for examples) |
| created_at | string | no | ISO 8601 timestamp |
| confidence | float | no | Extraction confidence 0-1. Default: 1.0 (manually verified) |

**Validation rules**:
- `id` must be unique within the graph
- `node_type` must be a valid NodeType enum value
- `difficulty` must be in [0.0, 1.0]
- `confidence` must be in [0.0, 1.0]
- `domain` must be one of: math, physics, chemistry, biology, cs

### KnowledgeEdge

A directed relationship between two nodes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source_id | string | yes | ID of the source node |
| target_id | string | yes | ID of the target node |
| edge_type | enum | yes | One of 10 EdgeType values |
| weight | float | no | Relation strength 0-1. Default: 1.0 |
| metadata | dict | no | Additional context |

**Edge types and semantics**:

| EdgeType | Direction meaning (A → B) | Example |
|----------|---------------------------|---------|
| PREREQUISITE | A must be understood before B | algebra → calculus |
| PART_OF | A is a subtopic of B | chain_rule → derivatives |
| GENERALIZES | A is a general case of B | L'Hopital → limits |
| CONFUSED_WITH | Students confuse A with B | product_rule ↔ chain_rule |
| COMMON_ERROR_FOR | Misconception A is typical error for B | sign_error → quadratic_formula |
| APPLIES_TO | Method A solves/applies to concept B | substitution → integrals |
| DERIVED_FROM | B is derived/proven from A | FTC → definite_integrals |
| PROVES | Theorem A proves/establishes B | MVT → Rolle's theorem |
| BEST_TAUGHT_AFTER | Pedagogically optimal to teach A after B | optimization → derivatives |
| ILLUSTRATES | Example A demonstrates concept B | example_chain_rule → chain_rule |

**Validation rules**:
- Both `source_id` and `target_id` must exist in the graph
- `edge_type` must be a valid EdgeType enum value
- No self-loops (`source_id != target_id`)

### FrontierNode (output only)

A concept at the edge of the student's knowledge.

| Field | Type | Description |
|-------|------|-------------|
| node_id | string | Knowledge graph node ID |
| title | string | Human-readable title |
| readiness_score | float | 0-1, how ready the student is |
| mastered_prereqs | list[string] | Prerequisite IDs mastered |
| missing_prereqs | list[string] | Prerequisite IDs not mastered |
| prereq_mastery_avg | float | Average mastery across prerequisites |
| own_mastery | float | Student's current mastery |
| difficulty | float | Concept difficulty |

### GapDiagnosis (output only)

Why a student failed at a concept.

| Field | Type | Description |
|-------|------|-------------|
| failed_concept | string | Concept the student struggled with |
| missing_prerequisites | list[string] | Unmastered prereqs, sorted by depth |
| root_gap | string or null | Deepest unmastered prerequisite (root cause) |
| suggested_review_path | list[string] | Ordered concepts to review |
| misconceptions | list[string] | Related misconception node IDs |
| confidence | float | Diagnosis confidence 0-1 |

### LearningPath (output only)

Optimal path from current knowledge to target.

| Field | Type | Description |
|-------|------|-------------|
| target | string | Target concept node ID |
| path | list[string] | Ordered node IDs to traverse |
| total_cost | float | Cumulative traversal cost |
| estimated_concepts_to_learn | int | Number of new concepts on path |
| mastery_along_path | list[float] | Mastery at each node |

## Relationships

```text
KnowledgeNode ──EdgeType──> KnowledgeNode
     │
     ├── CONCEPT ──PREREQUISITE──> CONCEPT
     ├── FORMULA ──DERIVED_FROM──> CONCEPT
     ├── EXAMPLE ──ILLUSTRATES──> CONCEPT
     ├── METHOD  ──APPLIES_TO──> CONCEPT
     ├── MISCONCEPTION ──COMMON_ERROR_FOR──> CONCEPT
     ├── CONCEPT ──CONFUSED_WITH──> CONCEPT
     ├── CONCEPT ──PART_OF──> CONCEPT
     ├── CONCEPT ──GENERALIZES──> CONCEPT
     ├── THEOREM ──PROVES──> CONCEPT
     └── CONCEPT ──BEST_TAUGHT_AFTER──> CONCEPT

PersonalizedNavigator = KnowledgeGraph + MasteryProvider(StudentMemory)
     │
     ├── get_learning_frontier() → List[FrontierNode]
     ├── diagnose_gap() → GapDiagnosis
     ├── find_optimal_path() → LearningPath
     └── get_concept_context() → Dict (enriched with student mastery)
```

## State Transitions

**KnowledgeNode confidence lifecycle**:
```
Extracted (confidence < 1.0) → Reviewed (confidence = 1.0) → Updated (confidence = 1.0)
```

**Graph growth**:
```
Empty → Seeded (migration) → Growing (source extraction) → Refined (session feedback)
```

## Persistence Format

```json
{
  "version": "1.0",
  "saved_at": "2026-04-16T12:00:00",
  "nodes": [
    {
      "id": "math:derivative:definition",
      "node_type": "concept",
      "title": "Производная",
      "title_en": "Derivative",
      "content": "Производная функции f(x) в точке x₀ ...",
      "domain": "math",
      "tags": ["calculus", "differentiation"],
      "difficulty": 0.5,
      "source": "skill_graph_migration",
      "confidence": 1.0
    }
  ],
  "edges": [
    {
      "source_id": "math:limits:definition",
      "target_id": "math:derivative:definition",
      "edge_type": "prerequisite",
      "weight": 1.0
    }
  ]
}
```
