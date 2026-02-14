# Data Model: MITS Extended Features

**Date**: 2026-02-02
**Feature**: 007-mits-extended-features

## Overview

This document defines the data entities for MITS Extended Features. Entities are grouped by module and include relationships, validation rules, and state transitions where applicable.

---

## 1. Gamification Module

### 1.1 StudentXP

Tracks experience points and level for each student.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| student_id | string | PK, required | Unique student identifier |
| total_xp | integer | >= 0, default 0 | Cumulative experience points |
| level | integer | >= 1, default 1 | Current level (derived from total_xp) |
| xp_to_next_level | integer | computed | XP needed for next level |
| updated_at | datetime | auto | Last update timestamp |

**Level Progression Formula**:
```
level = floor(sqrt(total_xp / 100)) + 1
xp_for_level(n) = 100 * (n - 1)^2
```

**State Transitions**:
- `award_xp(amount)`: total_xp += amount; recalculate level
- `reset()`: total_xp = 0, level = 1 (admin only)

---

### 1.2 Achievement

Definition of unlockable achievements (static data).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | string | PK, required | Unique achievement ID |
| name | string | required, max 50 | Display name |
| description | string | required, max 200 | What user did to earn it |
| icon | string | optional | Emoji or icon reference |
| category | enum | progress/mastery/streak/challenge | Achievement type |
| criteria | json | required | Unlock conditions |
| xp_reward | integer | >= 0 | XP granted on unlock |
| rarity | enum | common/rare/epic/legendary | Determines visual styling |

**Criteria Schema**:
```json
{
  "type": "problems_solved",
  "count": 100,
  "topic": null  // null = any topic
}
```

**Example Achievements**:
```json
[
  {"id": "first_problem", "name": "First Steps", "criteria": {"type": "problems_solved", "count": 1}},
  {"id": "week_streak", "name": "Week Warrior", "criteria": {"type": "streak_days", "count": 7}},
  {"id": "algebra_master", "name": "Algebra Master", "criteria": {"type": "topic_mastery", "topic": "algebra", "threshold": 0.9}}
]
```

---

### 1.3 StudentAchievement

Tracks which achievements each student has unlocked.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| student_id | string | PK (composite) | Student reference |
| achievement_id | string | PK (composite), FK | Achievement reference |
| unlocked_at | datetime | required | When achievement was earned |
| notified | boolean | default false | User has seen notification |

**Relations**:
- StudentAchievement.student_id -> Student.id
- StudentAchievement.achievement_id -> Achievement.id

---

### 1.4 Streak

Tracks daily learning streaks.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| student_id | string | PK | Student reference |
| current_streak | integer | >= 0 | Current consecutive days |
| longest_streak | integer | >= 0 | All-time record |
| last_activity_date | date | required | Last day with activity |
| freeze_count | integer | >= 0, default 0 | Streak freezes available |
| updated_at | datetime | auto | Last update timestamp |

**State Transitions**:
- `record_activity(date)`:
  - If date == last_activity_date + 1 day: current_streak += 1
  - If date == last_activity_date: no change
  - If date > last_activity_date + 1 day: current_streak = 1 (or use freeze)
- `use_freeze()`: freeze_count -= 1; preserve streak
- `award_freeze()`: freeze_count += 1

---

## 2. Spaced Repetition Module

### 2.1 ReviewCard

Represents a topic to be reviewed with SM-2 parameters.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | string | PK, auto-generated | Unique card ID |
| student_id | string | FK, required | Student reference |
| topic | string | required | Topic/skill identifier |
| easiness_factor | float | >= 1.3, default 2.5 | SM-2 EF parameter |
| interval | integer | >= 1, default 1 | Days until next review |
| repetitions | integer | >= 0, default 0 | Successful review count |
| next_review_date | date | required | When card is due |
| last_review_date | date | nullable | Last review date |
| created_at | datetime | auto | Card creation time |

**SM-2 State Transitions**:
```
review(quality: 0-5):
  if quality >= 3:  # Successful
    if repetitions == 0: interval = 1
    elif repetitions == 1: interval = 6
    else: interval = round(interval * easiness_factor)
    repetitions += 1
  else:  # Failed
    repetitions = 0
    interval = 1

  easiness_factor = max(1.3, EF + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
  next_review_date = today + interval days
```

**Relations**:
- ReviewCard.student_id -> Student.id
- ReviewCard.topic -> SkillGraph.skill_id

---

### 2.2 ReviewHistory

Audit log of all reviews.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Unique record ID |
| card_id | string | FK, required | ReviewCard reference |
| reviewed_at | datetime | required | Review timestamp |
| quality | integer | 0-5 | User-rated quality |
| response_time_ms | integer | >= 0 | Time to answer |

---

## 3. Activity Tracking Module

### 3.1 ActivityLog

Records all learning sessions.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto-increment | Unique log ID |
| student_id | string | FK, required | Student reference |
| session_id | string | required | Session identifier |
| activity_type | enum | problem/review/hint/chat | Type of activity |
| topic | string | nullable | Related topic |
| problem_id | string | nullable | Problem reference |
| timestamp | datetime | required | When activity occurred |
| duration_seconds | integer | >= 0 | Time spent |
| success | boolean | nullable | Was attempt successful |
| metadata | json | nullable | Additional context |

**Indices**:
- (student_id, timestamp) for time-range queries
- (student_id, activity_type) for aggregations

---

### 3.2 DailyActivitySummary

Aggregated daily statistics (materialized for dashboard).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| student_id | string | PK (composite) | Student reference |
| date | date | PK (composite) | Activity date |
| problems_attempted | integer | >= 0 | Problems tried |
| problems_solved | integer | >= 0 | Problems completed |
| time_spent_minutes | integer | >= 0 | Total study time |
| topics_practiced | json | array | List of topics |
| xp_earned | integer | >= 0 | XP gained that day |

---

## 4. Export Module

### 4.1 ExportProfile

Schema for JSON profile export.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "exported_at", "profile"],
  "properties": {
    "version": {"type": "string", "pattern": "^\\d+\\.\\d+$"},
    "exported_at": {"type": "string", "format": "date-time"},
    "profile": {
      "type": "object",
      "required": ["student_id", "mastery", "gamification"],
      "properties": {
        "student_id": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "mastery": {
          "type": "object",
          "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "gamification": {
          "type": "object",
          "properties": {
            "xp": {"type": "integer", "minimum": 0},
            "level": {"type": "integer", "minimum": 1},
            "achievements": {"type": "array", "items": {"type": "string"}},
            "streak": {
              "type": "object",
              "properties": {
                "current": {"type": "integer"},
                "longest": {"type": "integer"}
              }
            }
          }
        },
        "spaced_repetition": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "topic": {"type": "string"},
              "easiness_factor": {"type": "number"},
              "interval": {"type": "integer"},
              "next_review": {"type": "string", "format": "date"}
            }
          }
        },
        "activity_summary": {
          "type": "object",
          "properties": {
            "total_problems": {"type": "integer"},
            "total_time_hours": {"type": "number"},
            "first_activity": {"type": "string", "format": "date"},
            "last_activity": {"type": "string", "format": "date"}
          }
        }
      }
    }
  }
}
```

---

## 5. API Module

### 5.1 APIToken

JWT token storage for API authentication.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | string | PK, auto-generated | Token ID (jti claim) |
| student_id | string | FK, required | Token owner |
| token_hash | string | required | SHA-256 of token |
| scopes | json | array | Permitted operations |
| created_at | datetime | auto | Token creation time |
| expires_at | datetime | required | Token expiration |
| revoked | boolean | default false | Manual revocation flag |
| last_used_at | datetime | nullable | Last API call time |

**Scopes**:
- `chat:read` - Read chat history
- `chat:write` - Send messages
- `profile:read` - View profile
- `profile:write` - Modify profile
- `progress:read` - View progress data

---

### 5.2 RateLimitEntry

Tracks API rate limits per token.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| token_id | string | PK (composite) | Token reference |
| window_start | datetime | PK (composite) | Rate limit window |
| request_count | integer | >= 0 | Requests in window |

**Rate Limits**:
- Default: 60 requests per minute
- Chat endpoints: 10 requests per minute
- Export: 1 request per hour

---

## 6. Embedding Cache Module

### 6.1 EmbeddingCache

Persistent cache for computed embeddings.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| content_hash | string | PK | SHA-256 of input text |
| embedding | blob | required | Float32 vector (384 dims) |
| model_version | string | required | Embedding model identifier |
| created_at | datetime | auto | Cache entry creation |
| last_accessed | datetime | auto | Last retrieval time |
| access_count | integer | >= 0, default 0 | Hit counter |

**Eviction Policy**:
- Maximum entries: 100,000
- Evict by: last_accessed ASC (LRU)
- Batch eviction: Remove 10% oldest when limit reached

---

## Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────────┐
│   Student   │───────│    StudentXP     │
└─────────────┘       └──────────────────┘
      │                        │
      │               ┌────────┴────────┐
      │               ▼                 ▼
      │       ┌─────────────┐   ┌─────────────┐
      │       │   Streak    │   │StudentAchiev│
      │       └─────────────┘   └──────┬──────┘
      │                                │
      │                        ┌───────┴───────┐
      │                        ▼               │
      │                 ┌─────────────┐        │
      │                 │ Achievement │◄───────┘
      │                 └─────────────┘
      │
      ├─────────────────┬─────────────────┐
      ▼                 ▼                 ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ ReviewCard  │  │ ActivityLog │  │  APIToken   │
└──────┬──────┘  └─────────────┘  └─────────────┘
       │
       ▼
┌──────────────┐
│ReviewHistory │
└──────────────┘
```

---

## Database Schema (SQLite)

```sql
-- Gamification
CREATE TABLE student_xp (
    student_id TEXT PRIMARY KEY,
    total_xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE achievements (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    icon TEXT,
    category TEXT CHECK(category IN ('progress', 'mastery', 'streak', 'challenge')),
    criteria TEXT NOT NULL,  -- JSON
    xp_reward INTEGER DEFAULT 0,
    rarity TEXT CHECK(rarity IN ('common', 'rare', 'epic', 'legendary'))
);

CREATE TABLE student_achievements (
    student_id TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    unlocked_at DATETIME NOT NULL,
    notified INTEGER DEFAULT 0,
    PRIMARY KEY (student_id, achievement_id),
    FOREIGN KEY (achievement_id) REFERENCES achievements(id)
);

CREATE TABLE streaks (
    student_id TEXT PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_activity_date DATE,
    freeze_count INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Spaced Repetition
CREATE TABLE review_cards (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    easiness_factor REAL DEFAULT 2.5,
    interval INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0,
    next_review_date DATE NOT NULL,
    last_review_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE review_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    reviewed_at DATETIME NOT NULL,
    quality INTEGER CHECK(quality BETWEEN 0 AND 5),
    response_time_ms INTEGER,
    FOREIGN KEY (card_id) REFERENCES review_cards(id)
);

-- Activity
CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    activity_type TEXT CHECK(activity_type IN ('problem', 'review', 'hint', 'chat')),
    topic TEXT,
    problem_id TEXT,
    timestamp DATETIME NOT NULL,
    duration_seconds INTEGER DEFAULT 0,
    success INTEGER,
    metadata TEXT  -- JSON
);

CREATE INDEX idx_activity_student_time ON activity_log(student_id, timestamp);

-- API
CREATE TABLE api_tokens (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    scopes TEXT NOT NULL,  -- JSON array
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    revoked INTEGER DEFAULT 0,
    last_used_at DATETIME
);

-- Embedding Cache
CREATE TABLE embedding_cache (
    content_hash TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model_version TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0
);

CREATE INDEX idx_cache_lru ON embedding_cache(last_accessed);
```
