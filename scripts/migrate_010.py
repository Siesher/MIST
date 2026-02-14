#!/usr/bin/env python3
"""
Database Migration Script for Feature 010: Performance Optimization

Creates new tables and extends existing ones for:
- A/B experiments and assignments
- Resource samples
- Metrics reports
- Extended session metrics
"""

import sqlite3
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_db_path() -> Path:
    """Get metrics database path."""
    return Path("./data/metrics.db")


def migrate(db_path: Path = None) -> None:
    """Run database migration."""
    if db_path is None:
        db_path = get_db_path()

    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print(f"Migrating database: {db_path}")

    # ─────────────────────────────────────────────────────────────
    # Extend sessions table with new columns (if table exists)
    # ─────────────────────────────────────────────────────────────

    # Check if sessions table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='sessions'
    """)

    if cursor.fetchone():
        # Get existing columns
        cursor.execute("PRAGMA table_info(sessions)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        new_cols = [
            ("avg_response_time_ms", "REAL"),
            ("cache_hit_count", "INTEGER DEFAULT 0"),
            ("cache_miss_count", "INTEGER DEFAULT 0"),
            ("total_tokens_in", "INTEGER DEFAULT 0"),
            ("total_tokens_out", "INTEGER DEFAULT 0"),
            ("peak_vram_mb", "INTEGER"),
            ("context_compressions", "INTEGER DEFAULT 0"),
            ("ab_variant", "TEXT"),
            ("few_shot_used", "INTEGER DEFAULT 0"),
            ("cot_used", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}")
                    print(f"  Added column: sessions.{col_name}")
                except sqlite3.OperationalError as e:
                    print(f"  Skipped column sessions.{col_name}: {e}")
    else:
        print("  Sessions table not found, creating...")
        cursor.execute("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                task_id TEXT,
                topic TEXT,
                difficulty TEXT,
                outcome TEXT,
                hints_used INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                duration_seconds INTEGER DEFAULT 0,
                avg_response_time_ms REAL,
                cache_hit_count INTEGER DEFAULT 0,
                cache_miss_count INTEGER DEFAULT 0,
                total_tokens_in INTEGER DEFAULT 0,
                total_tokens_out INTEGER DEFAULT 0,
                peak_vram_mb INTEGER,
                context_compressions INTEGER DEFAULT 0,
                ab_variant TEXT,
                few_shot_used INTEGER DEFAULT 0,
                cot_used INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP
            )
        """)
        print("  Created sessions table")

    # ─────────────────────────────────────────────────────────────
    # Create ab_experiments table
    # ─────────────────────────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ab_experiments (
            experiment_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            variants_json TEXT NOT NULL,
            allocation_weights_json TEXT NOT NULL,
            target_metric TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            min_sessions INTEGER DEFAULT 100
        )
    """)
    print("  Created/verified ab_experiments table")

    # ─────────────────────────────────────────────────────────────
    # Create ab_assignments table
    # ─────────────────────────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ab_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES ab_experiments(experiment_id)
        )
    """)
    print("  Created/verified ab_assignments table")

    # ─────────────────────────────────────────────────────────────
    # Create resource_samples table
    # ─────────────────────────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resource_samples (
            sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ram_used_mb INTEGER,
            ram_available_mb INTEGER,
            vram_used_mb INTEGER,
            vram_total_mb INTEGER,
            gpu_utilization_percent REAL,
            cpu_percent REAL,
            active_sessions INTEGER DEFAULT 0,
            alert_triggered INTEGER DEFAULT 0,
            alert_type TEXT
        )
    """)
    print("  Created/verified resource_samples table")

    # ─────────────────────────────────────────────────────────────
    # Create metrics_reports table
    # ─────────────────────────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics_reports (
            report_id TEXT PRIMARY KEY,
            report_type TEXT NOT NULL,
            period_start TIMESTAMP,
            period_end TIMESTAMP,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metrics_json TEXT NOT NULL,
            charts_json TEXT,
            export_paths_json TEXT
        )
    """)
    print("  Created/verified metrics_reports table")

    # ─────────────────────────────────────────────────────────────
    # Create indexes for performance
    # ─────────────────────────────────────────────────────────────

    indexes = [
        ("idx_ab_assignments_experiment", "ab_assignments", "experiment_id"),
        ("idx_ab_assignments_session", "ab_assignments", "session_id"),
        ("idx_resource_samples_timestamp", "resource_samples", "timestamp"),
        ("idx_metrics_reports_type_period", "metrics_reports", "report_type, period_start"),
    ]

    for idx_name, table, cols in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({cols})")
            print(f"  Created/verified index: {idx_name}")
        except sqlite3.OperationalError as e:
            print(f"  Skipped index {idx_name}: {e}")

    conn.commit()
    conn.close()

    print("\nMigration completed successfully!")


def verify_schema(db_path: Path = None) -> bool:
    """Verify database schema after migration."""
    if db_path is None:
        db_path = get_db_path()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    required_tables = [
        "sessions",
        "ab_experiments",
        "ab_assignments",
        "resource_samples",
        "metrics_reports",
    ]

    print(f"\nVerifying schema in: {db_path}")

    all_ok = True
    for table in required_tables:
        cursor.execute(f"""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='{table}'
        """)
        if cursor.fetchone():
            # Count columns
            cursor.execute(f"PRAGMA table_info({table})")
            col_count = len(cursor.fetchall())
            print(f"  {table}: OK ({col_count} columns)")
        else:
            print(f"  {table}: MISSING!")
            all_ok = False

    conn.close()
    return all_ok


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database migration for feature 010")
    parser.add_argument("--db", type=str, help="Custom database path")
    parser.add_argument("--verify", action="store_true", help="Only verify schema")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None

    if args.verify:
        success = verify_schema(db_path)
        sys.exit(0 if success else 1)
    else:
        migrate(db_path)
        verify_schema(db_path)
