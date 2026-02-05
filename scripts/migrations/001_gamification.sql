-- Migration 001: Gamification Tables
-- Created: 2026-02-02

-- Student XP and level tracking
CREATE TABLE IF NOT EXISTS student_xp (
    student_id TEXT PRIMARY KEY,
    total_xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Achievement definitions (loaded from JSON, cached here)
CREATE TABLE IF NOT EXISTS achievements (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    icon TEXT,
    category TEXT CHECK(category IN ('progress', 'mastery', 'streak', 'challenge')),
    criteria TEXT NOT NULL,  -- JSON
    xp_reward INTEGER DEFAULT 0,
    rarity TEXT CHECK(rarity IN ('common', 'rare', 'epic', 'legendary'))
);

-- Student achievements (unlocked)
CREATE TABLE IF NOT EXISTS student_achievements (
    student_id TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    unlocked_at DATETIME NOT NULL,
    notified INTEGER DEFAULT 0,
    PRIMARY KEY (student_id, achievement_id),
    FOREIGN KEY (achievement_id) REFERENCES achievements(id)
);

-- Daily streaks
CREATE TABLE IF NOT EXISTS streaks (
    student_id TEXT PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_activity_date DATE,
    freeze_count INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_student_xp_level ON student_xp(level);
CREATE INDEX IF NOT EXISTS idx_student_achievements_student ON student_achievements(student_id);
CREATE INDEX IF NOT EXISTS idx_streaks_last_activity ON streaks(last_activity_date);
