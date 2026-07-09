"""
Metrics API Contract - Performance Optimization Feature

Internal Python API for metrics collection, A/B testing, and report generation.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class MetricType(Enum):
    """Types of metrics collected."""
    RESPONSE_TIME = "response_time"
    CACHE_HIT = "cache_hit"
    TOKEN_COUNT = "token_count"
    VRAM_USAGE = "vram_usage"
    SUCCESS_RATE = "success_rate"
    TELLING_RATE = "telling_rate"


class ExperimentStatus(Enum):
    """A/B experiment status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ReportType(Enum):
    """Types of generated reports."""
    DAILY = "daily"
    WEEKLY = "weekly"
    EXPERIMENT = "experiment"
    CUSTOM = "custom"


@dataclass
class SessionMetricsInput:
    """Metrics to record for a session."""
    session_id: str
    response_time_ms: float
    cache_hit: bool
    tokens_in: int
    tokens_out: int
    vram_mb: Optional[int] = None
    teaching_strategy: Optional[str] = None
    few_shot_used: bool = False
    cot_used: bool = False


@dataclass
class ABExperimentConfig:
    """Configuration for an A/B experiment."""
    experiment_id: str
    name: str
    description: str
    variants: List[Dict[str, Any]]  # [{"id": "control", "config": {...}}, ...]
    allocation_weights: List[float]  # [0.5, 0.5] for 50/50 split
    target_metric: str
    min_sessions: int = 100


@dataclass
class ABAssignment:
    """A/B variant assignment for a session."""
    experiment_id: str
    session_id: str
    variant_id: str
    variant_config: Dict[str, Any]


@dataclass
class ExperimentResults:
    """Results of an A/B experiment."""
    experiment_id: str
    status: ExperimentStatus
    total_sessions: int
    variants_data: List[Dict[str, Any]]  # Per-variant metrics
    winner: Optional[str]  # Variant ID of winner if significant
    confidence: Optional[float]  # Statistical confidence
    recommendation: str  # Human-readable recommendation


@dataclass
class ResourceSample:
    """Point-in-time resource usage sample."""
    timestamp: datetime
    ram_used_mb: int
    ram_available_mb: int
    vram_used_mb: int
    vram_total_mb: int
    gpu_utilization_percent: float
    cpu_percent: float
    active_sessions: int = 0


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    report_type: ReportType
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    experiment_id: Optional[str] = None  # For experiment reports
    include_charts: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["json", "csv"])


@dataclass
class GeneratedReport:
    """Generated metrics report."""
    report_id: str
    report_type: ReportType
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    metrics: Dict[str, Any]
    chart_paths: List[str]  # Paths to generated chart images
    export_paths: Dict[str, str]  # {"json": "path", "csv": "path"}


# API Functions (Contract Signatures)

# === Session Metrics ===

def record_session_metrics(metrics: SessionMetricsInput) -> None:
    """
    Record metrics for a single session interaction.

    Args:
        metrics: Session metrics to record

    Notes:
        - Called after each tutor response
        - Async to not block response delivery
    """
    ...


def get_session_summary(session_id: str) -> Dict[str, Any]:
    """
    Get aggregated metrics for a session.

    Args:
        session_id: Session to summarize

    Returns:
        Dictionary with aggregated metrics
    """
    ...


# === A/B Testing ===

def create_experiment(config: ABExperimentConfig) -> str:
    """
    Create a new A/B experiment.

    Args:
        config: Experiment configuration

    Returns:
        Experiment ID

    Raises:
        ValueError: If allocation_weights don't sum to 1.0
    """
    ...


def start_experiment(experiment_id: str) -> None:
    """
    Start an A/B experiment (set status to active).

    Args:
        experiment_id: Experiment to start

    Raises:
        ValueError: If experiment not in draft status
    """
    ...


def get_variant(experiment_id: str, session_id: str) -> ABAssignment:
    """
    Get A/B variant assignment for a session.

    Args:
        experiment_id: Active experiment ID
        session_id: Session to assign

    Returns:
        ABAssignment with variant ID and config

    Notes:
        - Deterministic: same session always gets same variant
        - Uses hash of session_id for random but repeatable assignment
    """
    ...


def record_experiment_outcome(
    experiment_id: str,
    session_id: str,
    metrics: Dict[str, float]
) -> None:
    """
    Record outcome metrics for an experiment session.

    Args:
        experiment_id: Experiment ID
        session_id: Session ID
        metrics: Outcome metrics (e.g., {"success": 1, "response_time_ms": 1500})
    """
    ...


def get_experiment_results(experiment_id: str) -> ExperimentResults:
    """
    Get current results of an experiment.

    Args:
        experiment_id: Experiment to analyze

    Returns:
        ExperimentResults with per-variant data and winner
    """
    ...


def stop_experiment(experiment_id: str) -> ExperimentResults:
    """
    Stop an experiment and get final results.

    Args:
        experiment_id: Experiment to stop

    Returns:
        Final ExperimentResults
    """
    ...


# === Resource Monitoring ===

def sample_resources() -> ResourceSample:
    """
    Take a point-in-time sample of system resources.

    Returns:
        ResourceSample with current usage

    Notes:
        - Uses psutil for RAM/CPU
        - Uses pynvml for GPU/VRAM
    """
    ...


def start_resource_monitoring(interval_seconds: int = 30) -> None:
    """
    Start background resource monitoring.

    Args:
        interval_seconds: Sampling interval

    Notes:
        - Runs in background thread
        - Stores samples in metrics.db
        - Triggers alerts if thresholds exceeded
    """
    ...


def stop_resource_monitoring() -> None:
    """Stop background resource monitoring."""
    ...


def get_resource_trend(
    start_time: datetime,
    end_time: datetime
) -> List[ResourceSample]:
    """
    Get resource usage trend over time.

    Args:
        start_time: Start of period
        end_time: End of period

    Returns:
        List of ResourceSamples in the period
    """
    ...


# === Report Generation ===

def generate_report(config: ReportConfig) -> GeneratedReport:
    """
    Generate a metrics report.

    Args:
        config: Report configuration

    Returns:
        GeneratedReport with paths to exported files

    Notes:
        - Generates charts with matplotlib/seaborn
        - Exports to data/reports/ directory
    """
    ...


def get_daily_summary(date: datetime) -> Dict[str, Any]:
    """
    Get summary metrics for a specific date.

    Args:
        date: Date to summarize

    Returns:
        Dictionary with daily aggregated metrics
    """
    ...


def get_performance_dashboard_data() -> Dict[str, Any]:
    """
    Get data for UI performance dashboard.

    Returns:
        Dictionary with:
        - current_metrics: Real-time stats
        - trends: Recent trends (last 7 days)
        - alerts: Any active alerts
        - experiments: Active A/B experiments
    """
    ...
