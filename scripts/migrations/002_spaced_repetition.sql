-- Migration 002: Spaced Repetition Tables
-- Created: 2026-02-02

-- Review cards (SM-2 algorithm)
CREATE TABLE IF NOT EXISTS review_cards (
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

-- Review history for analytics
CREATE TABLE IF NOT EXISTS review_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    reviewed_at DATETIME NOT NULL,
    quality INTEGER CHECK(quality BETWEEN 0 AND 5),
    response_time_ms INTEGER,
    FOREIGN KEY (card_id) REFERENCES review_cards(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_review_cards_student ON review_cards(student_id);
CREATE INDEX IF NOT EXISTS idx_review_cards_next_review ON review_cards(next_review_date);
CREATE INDEX IF NOT EXISTS idx_review_cards_topic ON review_cards(topic);
CREATE INDEX IF NOT EXISTS idx_review_history_card ON review_history(card_id);
