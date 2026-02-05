"""
A/B Testing Framework for MITS.

Provides session-level A/B variant assignment with SQLite tracking
for comparing different prompting strategies.

Feature 010: Performance Optimization
"""

import sqlite3
import json
import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class ABVariant:
    """Configuration for an A/B test variant."""

    variant_id: str
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    # Expected config keys:
    # - use_cot: bool
    # - use_few_shot: bool
    # - few_shot_count: int
    # - temperature: float
    # - system_prompt_variant: str

    sessions_count: int = 0
    metrics_summary: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ABVariant':
        return cls(**data)


@dataclass
class ABExperiment:
    """A/B experiment configuration and state."""

    experiment_id: str
    name: str
    description: str = ""

    variants: List[ABVariant] = field(default_factory=list)
    allocation_weights: List[float] = field(default_factory=list)

    target_metric: str = "success_rate"
    min_sessions: int = 100
    status: str = "draft"  # draft, active, paused, completed

    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "variants": [v.to_dict() for v in self.variants],
            "allocation_weights": self.allocation_weights,
            "target_metric": self.target_metric,
            "min_sessions": self.min_sessions,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


@dataclass
class ABAssignment:
    """Assignment of a session to a variant."""

    experiment_id: str
    session_id: str
    variant_id: str
    variant_config: Dict[str, Any] = field(default_factory=dict)
    assigned_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExperimentResults:
    """Results of an A/B experiment."""

    experiment_id: str
    status: str
    total_sessions: int
    variants_data: List[Dict[str, Any]]
    winner: Optional[str] = None
    confidence: Optional[float] = None
    recommendation: str = ""


class ABTestingManager:
    """
    Manages A/B experiments for MITS.

    Features:
    - Create and manage experiments
    - Deterministic session-to-variant assignment
    - Track experiment outcomes
    - Statistical analysis of results
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize AB testing manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path or Path("./data/metrics.db")
        self._experiments: Dict[str, ABExperiment] = {}
        self._init_db()
        self._load_experiments()

    def _init_db(self):
        """Initialize database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Experiments table
            conn.execute("""
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

            # Assignments table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ab_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (experiment_id) REFERENCES ab_experiments(experiment_id)
                )
            """)

            # Outcomes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ab_outcomes (
                    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (experiment_id) REFERENCES ab_experiments(experiment_id)
                )
            """)

            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ab_assignments_experiment
                ON ab_assignments(experiment_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ab_assignments_session
                ON ab_assignments(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ab_outcomes_experiment
                ON ab_outcomes(experiment_id)
            """)

    def _load_experiments(self):
        """Load existing experiments from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT experiment_id, name, description, variants_json,
                           allocation_weights_json, target_metric, status,
                           created_at, started_at, ended_at, min_sessions
                    FROM ab_experiments
                """)

                for row in cursor.fetchall():
                    variants_data = json.loads(row[3])
                    variants = [ABVariant.from_dict(v) for v in variants_data]

                    exp = ABExperiment(
                        experiment_id=row[0],
                        name=row[1],
                        description=row[2] or "",
                        variants=variants,
                        allocation_weights=json.loads(row[4]),
                        target_metric=row[5],
                        status=row[6],
                        created_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
                        started_at=datetime.fromisoformat(row[8]) if row[8] else None,
                        ended_at=datetime.fromisoformat(row[9]) if row[9] else None,
                        min_sessions=row[10] or 100,
                    )
                    self._experiments[exp.experiment_id] = exp

                logger.info(f"Loaded {len(self._experiments)} A/B experiments")

        except Exception as e:
            logger.error(f"Failed to load experiments: {e}")

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        variants: List[Dict[str, Any]],
        allocation_weights: List[float],
        target_metric: str = "success_rate",
        description: str = "",
        min_sessions: int = 100
    ) -> ABExperiment:
        """
        Create a new A/B experiment.

        Args:
            experiment_id: Unique experiment identifier
            name: Human-readable name
            variants: List of variant configurations
            allocation_weights: Weights for random assignment (must sum to 1.0)
            target_metric: Primary metric to optimize
            description: Experiment description
            min_sessions: Minimum sessions for statistical significance

        Returns:
            Created ABExperiment

        Raises:
            ValueError: If weights don't sum to 1.0 or less than 2 variants
        """
        if len(variants) < 2:
            raise ValueError("Experiment must have at least 2 variants")

        if abs(sum(allocation_weights) - 1.0) > 0.01:
            raise ValueError(f"Allocation weights must sum to 1.0, got {sum(allocation_weights)}")

        if len(variants) != len(allocation_weights):
            raise ValueError("Number of variants must match number of weights")

        # Create variant objects
        variant_objects = []
        for i, v in enumerate(variants):
            variant_objects.append(ABVariant(
                variant_id=v.get("id", f"variant_{i}"),
                name=v.get("name", f"Variant {i}"),
                config=v.get("config", {}),
            ))

        experiment = ABExperiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            variants=variant_objects,
            allocation_weights=allocation_weights,
            target_metric=target_metric,
            min_sessions=min_sessions,
        )

        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ab_experiments (
                    experiment_id, name, description, variants_json,
                    allocation_weights_json, target_metric, status,
                    created_at, min_sessions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment.experiment_id,
                experiment.name,
                experiment.description,
                json.dumps([v.to_dict() for v in experiment.variants]),
                json.dumps(experiment.allocation_weights),
                experiment.target_metric,
                experiment.status,
                experiment.created_at.isoformat(),
                experiment.min_sessions,
            ))

        self._experiments[experiment_id] = experiment
        logger.info(f"Created experiment: {experiment_id}")

        return experiment

    def start_experiment(self, experiment_id: str) -> None:
        """Start an experiment (set status to active)."""
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")

        exp = self._experiments[experiment_id]
        if exp.status != "draft":
            raise ValueError(f"Can only start experiments in 'draft' status, got '{exp.status}'")

        exp.status = "active"
        exp.started_at = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE ab_experiments
                SET status = ?, started_at = ?
                WHERE experiment_id = ?
            """, (exp.status, exp.started_at.isoformat(), experiment_id))

        logger.info(f"Started experiment: {experiment_id}")

    def pause_experiment(self, experiment_id: str) -> None:
        """Pause an active experiment."""
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")

        exp = self._experiments[experiment_id]
        exp.status = "paused"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE ab_experiments SET status = ? WHERE experiment_id = ?
            """, (exp.status, experiment_id))

        logger.info(f"Paused experiment: {experiment_id}")

    def stop_experiment(self, experiment_id: str) -> ExperimentResults:
        """Stop experiment and get final results."""
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")

        exp = self._experiments[experiment_id]
        exp.status = "completed"
        exp.ended_at = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE ab_experiments
                SET status = ?, ended_at = ?
                WHERE experiment_id = ?
            """, (exp.status, exp.ended_at.isoformat(), experiment_id))

        logger.info(f"Stopped experiment: {experiment_id}")
        return self.get_results(experiment_id)

    def get_variant(self, experiment_id: str, session_id: str) -> ABAssignment:
        """
        Get variant assignment for a session.

        Uses deterministic hash-based assignment for consistency.

        Args:
            experiment_id: Experiment to get variant from
            session_id: Session to assign

        Returns:
            ABAssignment with variant configuration
        """
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")

        exp = self._experiments[experiment_id]
        if exp.status != "active":
            raise ValueError(f"Experiment is not active: {exp.status}")

        # Check for existing assignment
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT variant_id FROM ab_assignments
                WHERE experiment_id = ? AND session_id = ?
            """, (experiment_id, session_id))
            row = cursor.fetchone()

            if row:
                # Return existing assignment
                variant_id = row[0]
                variant = next(
                    (v for v in exp.variants if v.variant_id == variant_id),
                    exp.variants[0]
                )
                return ABAssignment(
                    experiment_id=experiment_id,
                    session_id=session_id,
                    variant_id=variant_id,
                    variant_config=variant.config,
                )

        # Deterministic assignment based on session hash
        hash_input = f"{experiment_id}:{session_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        normalized = (hash_value % 10000) / 10000.0

        # Select variant based on weights
        cumulative = 0.0
        selected_variant = exp.variants[0]
        for variant, weight in zip(exp.variants, exp.allocation_weights):
            cumulative += weight
            if normalized <= cumulative:
                selected_variant = variant
                break

        # Save assignment
        assignment = ABAssignment(
            experiment_id=experiment_id,
            session_id=session_id,
            variant_id=selected_variant.variant_id,
            variant_config=selected_variant.config,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO ab_assignments (experiment_id, session_id, variant_id, assigned_at)
                VALUES (?, ?, ?, ?)
            """, (
                experiment_id,
                session_id,
                selected_variant.variant_id,
                assignment.assigned_at.isoformat(),
            ))

        logger.debug(f"Assigned {session_id} to variant {selected_variant.variant_id}")
        return assignment

    def record_outcome(
        self,
        experiment_id: str,
        session_id: str,
        metrics: Dict[str, float]
    ) -> None:
        """
        Record outcome metrics for a session.

        Args:
            experiment_id: Experiment ID
            session_id: Session ID
            metrics: Outcome metrics (e.g., {"success": 1, "response_time_ms": 1500})
        """
        # Get variant for this session
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT variant_id FROM ab_assignments
                WHERE experiment_id = ? AND session_id = ?
            """, (experiment_id, session_id))
            row = cursor.fetchone()

            if not row:
                logger.warning(f"No assignment found for session {session_id}")
                return

            variant_id = row[0]

            # Record outcome
            conn.execute("""
                INSERT INTO ab_outcomes (experiment_id, session_id, variant_id, metrics_json)
                VALUES (?, ?, ?, ?)
            """, (
                experiment_id,
                session_id,
                variant_id,
                json.dumps(metrics),
            ))

        logger.debug(f"Recorded outcome for {session_id}: {metrics}")

    def get_results(self, experiment_id: str) -> ExperimentResults:
        """
        Get current results of an experiment.

        Args:
            experiment_id: Experiment to analyze

        Returns:
            ExperimentResults with per-variant statistics
        """
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")

        exp = self._experiments[experiment_id]

        variants_data = []
        total_sessions = 0

        with sqlite3.connect(self.db_path) as conn:
            for variant in exp.variants:
                # Count sessions
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM ab_assignments
                    WHERE experiment_id = ? AND variant_id = ?
                """, (experiment_id, variant.variant_id))
                sessions = cursor.fetchone()[0]
                total_sessions += sessions

                # Get outcome metrics
                cursor = conn.execute("""
                    SELECT metrics_json FROM ab_outcomes
                    WHERE experiment_id = ? AND variant_id = ?
                """, (experiment_id, variant.variant_id))

                all_metrics: Dict[str, List[float]] = {}
                for row in cursor.fetchall():
                    metrics = json.loads(row[0])
                    for key, value in metrics.items():
                        if key not in all_metrics:
                            all_metrics[key] = []
                        all_metrics[key].append(float(value))

                # Calculate averages
                avg_metrics = {}
                for key, values in all_metrics.items():
                    if values:
                        avg_metrics[f"avg_{key}"] = sum(values) / len(values)
                        avg_metrics[f"count_{key}"] = len(values)

                variants_data.append({
                    "variant_id": variant.variant_id,
                    "name": variant.name,
                    "sessions": sessions,
                    "metrics": avg_metrics,
                })

        # Determine winner (simple comparison of target metric)
        winner = None
        best_value = None
        target_key = f"avg_{exp.target_metric}"

        for vd in variants_data:
            value = vd["metrics"].get(target_key)
            if value is not None:
                if best_value is None or value > best_value:
                    best_value = value
                    winner = vd["variant_id"]

        # Generate recommendation
        recommendation = ""
        if total_sessions < exp.min_sessions:
            recommendation = f"Need {exp.min_sessions - total_sessions} more sessions for significance"
        elif winner:
            recommendation = f"Variant '{winner}' performs best on {exp.target_metric}"
        else:
            recommendation = "Insufficient data for recommendation"

        return ExperimentResults(
            experiment_id=experiment_id,
            status=exp.status,
            total_sessions=total_sessions,
            variants_data=variants_data,
            winner=winner,
            confidence=None,  # Would need proper statistical test
            recommendation=recommendation,
        )

    def list_experiments(self) -> List[ABExperiment]:
        """List all experiments."""
        return list(self._experiments.values())

    def get_experiment(self, experiment_id: str) -> Optional[ABExperiment]:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)


# Global A/B testing manager
_ab_manager: Optional[ABTestingManager] = None


def get_ab_manager(db_path: Optional[Path] = None) -> ABTestingManager:
    """Get or create global A/B testing manager."""
    global _ab_manager
    if _ab_manager is None:
        if db_path is None:
            try:
                from src.config import settings
                db_path = settings.METRICS_DB_PATH
            except ImportError:
                db_path = Path("./data/metrics.db")
        _ab_manager = ABTestingManager(db_path)
    return _ab_manager


# Convenience functions
def get_variant(experiment_id: str, session_id: str) -> ABAssignment:
    """Get variant assignment for a session."""
    return get_ab_manager().get_variant(experiment_id, session_id)


def record_outcome(experiment_id: str, session_id: str, metrics: Dict[str, float]) -> None:
    """Record outcome metrics for a session."""
    get_ab_manager().record_outcome(experiment_id, session_id, metrics)
