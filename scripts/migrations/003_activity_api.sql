-- Migration 003: Activity Log and API Tokens
-- Created: 2026-02-02

-- Activity log for tracking all learning activities
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    activity_type TEXT CHECK(activity_type IN ('problem', 'review', 'hint', 'chat')),
    topic TEXT,
    problem_id TEXT,
    timestamp DATETIME NOT NULL,
    duration_seconds INTEGER DEFAULT 0,
    success INTEGER,
    metadata TEXT  -- JSON for additional context
);

-- Daily activity summary (materialized for dashboard performance)
CREATE TABLE IF NOT EXISTS daily_activity_summary (
    student_id TEXT NOT NULL,
    date DATE NOT NULL,
    problems_attempted INTEGER DEFAULT 0,
    problems_solved INTEGER DEFAULT 0,
    time_spent_minutes INTEGER DEFAULT 0,
    topics_practiced TEXT,  -- JSON array
    xp_earned INTEGER DEFAULT 0,
    PRIMARY KEY (student_id, date)
);

-- API tokens for REST API authentication
CREATE TABLE IF NOT EXISTS api_tokens (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    scopes TEXT NOT NULL,  -- JSON array
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    revoked INTEGER DEFAULT 0,
    last_used_at DATETIME
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_activity_log_student_time ON activity_log(student_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_log_type ON activity_log(activity_type);
CREATE INDEX IF NOT EXISTS idx_daily_summary_student ON daily_activity_summary(student_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_student ON api_tokens(student_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);
