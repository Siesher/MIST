#!/usr/bin/env python3
"""
Database initialization and migration script for MITS.

Creates SQLite tables for:
- Students
- Knowledge state
- Sessions
- Session turns
"""

import sqlite3
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings


def get_connection(db_path: Path = None) -> sqlite3.Connection:
    """Get database connection with WAL mode enabled."""
    if db_path is None:
        db_path = settings.STUDENT_MEMORY_DB_PATH

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all required tables."""

    cursor = conn.cursor()

    # Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            preferred_language TEXT DEFAULT 'ru',
            learning_style TEXT DEFAULT 'balanced',
            difficulty_preference TEXT DEFAULT 'medium',
            avg_response_time REAL DEFAULT 60.0,
            frustration_threshold INTEGER DEFAULT 3,
            total_sessions INTEGER DEFAULT 0,
            total_tasks_attempted INTEGER DEFAULT 0,
            total_tasks_solved INTEGER DEFAULT 0,
            last_active TIMESTAMP
        )
    """)

    # Knowledge state table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_state (
            student_id TEXT,
            topic_id TEXT,
            mastery REAL DEFAULT 0.3,
            p_learn REAL DEFAULT 0.1,
            p_forget REAL DEFAULT 0.05,
            p_guess REAL DEFAULT 0.2,
            p_slip REAL DEFAULT 0.1,
            last_practiced TIMESTAMP,
            practice_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            learning_velocity REAL DEFAULT 0.0,
            PRIMARY KEY (student_id, topic_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
        )
    """)

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            student_id TEXT,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            status TEXT DEFAULT 'active',
            tasks_attempted INTEGER DEFAULT 0,
            tasks_solved INTEGER DEFAULT 0,
            hints_given INTEGER DEFAULT 0,
            socratic_questions INTEGER DEFAULT 0,
            direct_answers INTEGER DEFAULT 0,
            telling_rate REAL DEFAULT 0.0,
            avg_cognitive_load TEXT DEFAULT 'optimal',
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
        )
    """)

    # Session turns (conversation history)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            turn_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            role TEXT,
            content TEXT,
            task_id TEXT,
            tutor_move TEXT,
            response_time_ms INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        )
    """)

    # Create indexes for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_student
        ON knowledge_state(student_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_student
        ON sessions(student_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_session
        ON turns(session_id)
    """)

    conn.commit()
    print("[OK] All tables created successfully")


def drop_all_tables(conn: sqlite3.Connection) -> None:
    """Drop all tables (for reset)."""
    cursor = conn.cursor()

    # Extended feature tables
    cursor.execute("DROP TABLE IF EXISTS embedding_cache")
    cursor.execute("DROP TABLE IF EXISTS api_tokens")
    cursor.execute("DROP TABLE IF EXISTS daily_activity_summary")
    cursor.execute("DROP TABLE IF EXISTS activity_log")
    cursor.execute("DROP TABLE IF EXISTS review_history")
    cursor.execute("DROP TABLE IF EXISTS review_cards")
    cursor.execute("DROP TABLE IF EXISTS student_achievements")
    cursor.execute("DROP TABLE IF EXISTS achievements")
    cursor.execute("DROP TABLE IF EXISTS streaks")
    cursor.execute("DROP TABLE IF EXISTS student_xp")

    # Core tables
    cursor.execute("DROP TABLE IF EXISTS turns")
    cursor.execute("DROP TABLE IF EXISTS sessions")
    cursor.execute("DROP TABLE IF EXISTS knowledge_state")
    cursor.execute("DROP TABLE IF EXISTS students")

    conn.commit()
    print("[OK] All tables dropped")


def run_migrations(conn: sqlite3.Connection, migrations_dir: Path = None) -> None:
    """Run SQL migration files from migrations directory."""
    if migrations_dir is None:
        migrations_dir = Path(__file__).parent.parent / "migrations"

    if not migrations_dir.exists():
        print(f"[WARN] Migrations directory not found: {migrations_dir}")
        return

    # Get list of migration files sorted by name
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("[WARN] No migration files found")
        return

    for migration_file in migration_files:
        print(f"Running migration: {migration_file.name}...")
        sql = migration_file.read_text(encoding="utf-8")

        try:
            # Use executescript for multi-statement SQL files
            conn.executescript(sql)
            print(f"  [OK] {migration_file.name}")
        except sqlite3.Error as e:
            print(f"  [WARN] Migration error: {e}")

    print(f"[OK] Ran {len(migration_files)} migrations")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize MITS database")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables")
    parser.add_argument("--extended", action="store_true", help="Run extended feature migrations (gamification, spaced repetition, etc.)")
    parser.add_argument("--db-path", type=Path, help="Custom database path")
    args = parser.parse_args()

    db_path = args.db_path or settings.STUDENT_MEMORY_DB_PATH
    print(f"Database path: {db_path}")

    conn = get_connection(db_path)

    try:
        if args.reset:
            print("Resetting database...")
            drop_all_tables(conn)

        create_tables(conn)

        if args.extended:
            print("\nRunning extended feature migrations...")
            run_migrations(conn)

        print(f"[OK] Database initialized at {db_path}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
