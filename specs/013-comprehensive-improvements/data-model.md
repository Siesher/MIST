# Data Model: MITS Comprehensive Improvements

**Date**: 2026-02-05
**Feature**: 013-comprehensive-improvements

## Entities

### User (NEW — Authentication)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| email | string | Unique, indexed |
| password_hash | string | Argon2 hash |
| display_name | string | Shown in UI |
| preferred_mode | enum | chat, guided_learning, task_generator |
| created_at | datetime | Registration time |
| last_login_at | datetime | Last login |

### Session (MODIFIED — Persistence)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| user_id | UUID | FK → User |
| mode | string | chat, guided_learning, task_generator |
| topic | string | nullable |
| difficulty | string | nullable |
| status | string | active, completed, abandoned |
| is_solved | boolean | default false |
| hints_used | int | default 0 |
| attempts | int | default 0 |
| task_json | JSON | Serialized task data |
| created_at | datetime | |
| updated_at | datetime | |

### Message (MODIFIED — Persistence)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| session_id | UUID | FK → Session |
| role | string | user, tutor, system |
| content | text | Message content |
| move_type | string | nullable, tutor move type |
| is_correct | boolean | nullable |
| thinking | text | nullable, model reasoning |
| timestamp | datetime | |

### SyntheticDialog (NEW — Training Data)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| topic | string | Math topic (derivatives, integrals, etc.) |
| difficulty | enum | easy, medium, hard, olympiad |
| student_type | string | strong, average, weak, frustrated, careless |
| turns | JSON[] | Array of turn objects |
| quality_score | float | 0-5, from verification |
| source | string | gpt4, claude, glm_self |
| created_at | datetime | |

#### Turn (embedded in SyntheticDialog.turns)

| Field | Type | Notes |
|-------|------|-------|
| speaker | string | tutor, student |
| text | string | Message content |
| move_type | string | scaffold, probe, clarify, affirm, correct, hint, tell |
| emotion | string | neutral, frustrated, confused, engaged, bored |
| error_type | string | nullable: conceptual, procedural, careless, notation |
| is_correct | boolean | nullable, for student turns |
| knowledge_component | string | nullable, skill tag |

### TrainingRun (NEW — ML Tracking)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| model_type | string | glm_qlora, dkt, rubert_affect |
| dataset | string | Dataset identifier |
| hyperparameters | JSON | lr, epochs, batch_size, etc. |
| metrics | JSON | loss, auc, f1, etc. |
| checkpoint_path | string | Path to saved weights |
| status | string | running, completed, failed |
| started_at | datetime | |
| completed_at | datetime | nullable |

### EvaluationReport (NEW — Benchmarks)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| report_type | string | model_comparison, knowledge_tracing, affect_detection, tutoring_quality |
| metrics | JSON | Dict of metric_name → value |
| model_a | string | Baseline model identifier |
| model_b | string | Comparison model identifier |
| dataset | string | Evaluation dataset used |
| statistical_tests | JSON | p-value, effect_size, confidence_interval |
| created_at | datetime | |

### Experiment (NEW — A/B Testing)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| name | string | Experiment name |
| description | text | |
| groups | JSON | [{name, mode, allocation_pct}] |
| pre_test_id | string | Reference to test instrument |
| post_test_id | string | Reference to test instrument |
| status | string | draft, enrolling, active, completed, analyzed |
| created_at | datetime | |
| completed_at | datetime | nullable |

### ExperimentParticipant (NEW — A/B Testing)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| experiment_id | UUID | FK → Experiment |
| user_id | UUID | FK → User |
| group_name | string | Assigned group |
| pre_score | float | nullable, pre-test score |
| post_score | float | nullable, post-test score |
| sessions_completed | int | Number of sessions done |
| enrolled_at | datetime | |

### AnalyticsSnapshot (NEW — Dashboard)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| user_id | UUID | FK → User |
| date | date | Snapshot date |
| sessions_count | int | Sessions that day |
| mastery_by_topic | JSON | {topic: mastery_score} |
| error_distribution | JSON | {error_type: count} |
| study_minutes | int | Active study time |

### RefreshToken (NEW — Authentication)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| user_id | UUID | FK → User |
| token_hash | string | Hashed refresh token |
| expires_at | datetime | |
| revoked | boolean | default false |
| created_at | datetime | |

## Relationships

```
User 1──* Session
User 1──* RefreshToken
User 1──* ExperimentParticipant
User 1──* AnalyticsSnapshot
Session 1──* Message
Experiment 1──* ExperimentParticipant
```

## State Transitions

### Session.status
```
active → completed (is_solved=true or user ends)
active → abandoned (timeout or user deletes)
```

### Experiment.status
```
draft → enrolling → active → completed → analyzed
```

### TrainingRun.status
```
running → completed
running → failed
```
