"""
Inference Metrics tracking for MITS.

Provides InferenceMetrics dataclass and MetricsCollector
for tracking model performance (latency, token rate, memory).

Extended in Feature 010 for:
- Cache hit rate tracking
- Resource monitoring (VRAM/RAM)
- Performance alerts
"""

import sqlite3
import time
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
import logging

logger = logging.getLogger(__name__)

# Optional dependencies for resource monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.info("psutil not installed. CPU/RAM monitoring unavailable.")

try:
    import pynvml
    pynvml.nvmlInit()
    HAS_PYNVML = True
except (ImportError, Exception):
    HAS_PYNVML = False
    logger.info("pynvml not available. GPU monitoring unavailable.")


@dataclass
class InferenceMetrics:
    """Performance metrics for a single inference request."""

    model_name: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    # Latency metrics
    time_to_first_token_ms: float = 0.0
    tokens_per_second: float = 0.0
    total_generation_time_ms: float = 0.0

    # Resource usage
    vram_used_mb: float = 0.0
    ram_used_mb: float = 0.0
    gpu_utilization_percent: float = 0.0

    # Token counts
    input_tokens: int = 0
    output_tokens: int = 0
    context_length_used: int = 0

    # Error tracking
    had_error: bool = False
    error_message: Optional[str] = None

    # Cache metrics (Feature 010)
    cache_hit: bool = False
    cache_hit_type: str = "miss"  # "exact", "semantic", "miss"
    cache_similarity: float = 0.0

    # Feature flags (010)
    few_shot_used: bool = False
    cot_used: bool = False
    context_compressed: bool = False

    # A/B testing (010)
    ab_variant: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "model_name": self.model_name,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "time_to_first_token_ms": self.time_to_first_token_ms,
            "tokens_per_second": self.tokens_per_second,
            "total_generation_time_ms": self.total_generation_time_ms,
            "vram_used_mb": self.vram_used_mb,
            "ram_used_mb": self.ram_used_mb,
            "gpu_utilization_percent": self.gpu_utilization_percent,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "context_length_used": self.context_length_used,
            "had_error": self.had_error,
            "error_message": self.error_message,
            # Feature 010 fields
            "cache_hit": self.cache_hit,
            "cache_hit_type": self.cache_hit_type,
            "cache_similarity": self.cache_similarity,
            "few_shot_used": self.few_shot_used,
            "cot_used": self.cot_used,
            "context_compressed": self.context_compressed,
            "ab_variant": self.ab_variant,
        }


class InferenceTimer:
    """Context manager for timing inference operations."""

    def __init__(self):
        self.start_time: float = 0.0
        self.first_token_time: Optional[float] = None
        self.end_time: float = 0.0
        self.token_count: int = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()

    def mark_first_token(self):
        """Mark when first token was received."""
        if self.first_token_time is None:
            self.first_token_time = time.perf_counter()

    def increment_tokens(self, count: int = 1):
        """Increment token count."""
        self.token_count += count

    @property
    def time_to_first_token_ms(self) -> float:
        """Get time to first token in milliseconds."""
        if self.first_token_time is None:
            return 0.0
        return (self.first_token_time - self.start_time) * 1000

    @property
    def total_time_ms(self) -> float:
        """Get total generation time in milliseconds."""
        return (self.end_time - self.start_time) * 1000

    @property
    def tokens_per_second(self) -> float:
        """Calculate tokens per second."""
        elapsed = self.end_time - self.start_time
        if elapsed <= 0 or self.token_count == 0:
            return 0.0
        return self.token_count / elapsed


class MetricsCollector:
    """Collects and stores inference metrics."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for metrics storage."""
        if self.db_path is None:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inference_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    time_to_first_token_ms REAL,
                    tokens_per_second REAL,
                    total_generation_time_ms REAL,
                    vram_used_mb REAL,
                    ram_used_mb REAL,
                    gpu_utilization_percent REAL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    context_length_used INTEGER,
                    had_error INTEGER,
                    error_message TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_model
                ON inference_metrics(model_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
                ON inference_metrics(timestamp)
            """)

    def log(self, metrics: InferenceMetrics):
        """Log metrics to database."""
        if self.db_path is None:
            logger.debug(f"Metrics (no DB): {metrics.to_dict()}")
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO inference_metrics (
                        model_name, session_id, timestamp,
                        time_to_first_token_ms, tokens_per_second, total_generation_time_ms,
                        vram_used_mb, ram_used_mb, gpu_utilization_percent,
                        input_tokens, output_tokens, context_length_used,
                        had_error, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metrics.model_name,
                    metrics.session_id,
                    metrics.timestamp.isoformat(),
                    metrics.time_to_first_token_ms,
                    metrics.tokens_per_second,
                    metrics.total_generation_time_ms,
                    metrics.vram_used_mb,
                    metrics.ram_used_mb,
                    metrics.gpu_utilization_percent,
                    metrics.input_tokens,
                    metrics.output_tokens,
                    metrics.context_length_used,
                    1 if metrics.had_error else 0,
                    metrics.error_message,
                ))
            logger.debug(f"Logged metrics for {metrics.model_name}")
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")

    def get_model_stats(self, model_name: str, hours: int = 24) -> Dict[str, float]:
        """Get average stats for a model over the last N hours."""
        if self.db_path is None:
            return {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT
                        AVG(time_to_first_token_ms) as avg_ttft,
                        AVG(tokens_per_second) as avg_tps,
                        AVG(total_generation_time_ms) as avg_total_time,
                        COUNT(*) as request_count,
                        SUM(CASE WHEN had_error = 1 THEN 1 ELSE 0 END) as error_count
                    FROM inference_metrics
                    WHERE model_name = ?
                    AND timestamp > datetime('now', ?)
                """, (model_name, f"-{hours} hours"))
                row = cursor.fetchone()

                if row and row[3] > 0:
                    return {
                        "avg_ttft_ms": row[0] or 0.0,
                        "avg_tps": row[1] or 0.0,
                        "avg_total_time_ms": row[2] or 0.0,
                        "request_count": row[3],
                        "error_rate": row[4] / row[3] if row[3] > 0 else 0.0,
                    }
        except Exception as e:
            logger.error(f"Failed to get model stats: {e}")

        return {}

    def check_performance_thresholds(
        self,
        metrics: InferenceMetrics,
        max_ttft_ms: float = 3000.0,
        min_tps: float = 5.0,
    ) -> list[str]:
        """Check if metrics exceed thresholds, return list of warnings."""
        warnings = []

        if metrics.time_to_first_token_ms > max_ttft_ms:
            warnings.append(
                f"TTFT {metrics.time_to_first_token_ms:.0f}ms exceeds "
                f"threshold {max_ttft_ms:.0f}ms"
            )

        if metrics.tokens_per_second > 0 and metrics.tokens_per_second < min_tps:
            warnings.append(
                f"Token rate {metrics.tokens_per_second:.1f} t/s below "
                f"threshold {min_tps:.1f} t/s"
            )

        return warnings


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector(db_path: Optional[Path] = None) -> MetricsCollector:
    """Get or create global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(db_path)
    return _metrics_collector


# ═══════════════════════════════════════════════════════════════════════════
# RESOURCE MONITORING (Feature 010)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ResourceSample:
    """Point-in-time resource usage sample."""

    timestamp: datetime = field(default_factory=datetime.now)
    ram_used_mb: int = 0
    ram_available_mb: int = 0
    vram_used_mb: int = 0
    vram_total_mb: int = 0
    gpu_utilization_percent: float = 0.0
    cpu_percent: float = 0.0
    active_sessions: int = 0
    alert_triggered: bool = False
    alert_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "ram_used_mb": self.ram_used_mb,
            "ram_available_mb": self.ram_available_mb,
            "vram_used_mb": self.vram_used_mb,
            "vram_total_mb": self.vram_total_mb,
            "gpu_utilization_percent": self.gpu_utilization_percent,
            "cpu_percent": self.cpu_percent,
            "active_sessions": self.active_sessions,
            "alert_triggered": self.alert_triggered,
            "alert_type": self.alert_type,
        }


class ResourceMonitor:
    """
    Background resource monitoring for VRAM/RAM usage.

    Samples system resources at configurable intervals and
    triggers alerts when thresholds are exceeded.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        sample_interval_sec: int = 30,
        vram_alert_threshold_mb: int = 7000,
        ram_alert_threshold_mb: int = 14000,
        on_alert: Optional[Callable[[ResourceSample], None]] = None
    ):
        """
        Initialize ResourceMonitor.

        Args:
            db_path: Path to SQLite database for storing samples
            sample_interval_sec: Sampling interval in seconds
            vram_alert_threshold_mb: VRAM threshold for alerts
            ram_alert_threshold_mb: RAM threshold for alerts
            on_alert: Callback function when alert is triggered
        """
        self.db_path = db_path
        self.sample_interval = sample_interval_sec
        self.vram_threshold = vram_alert_threshold_mb
        self.ram_threshold = ram_alert_threshold_mb
        self.on_alert = on_alert

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._samples: List[ResourceSample] = []
        self._active_sessions = 0
        self._lock = threading.Lock()

        # Initialize database table
        if self.db_path:
            self._init_db()

        logger.info(
            f"ResourceMonitor initialized: interval={sample_interval_sec}s, "
            f"vram_threshold={vram_alert_threshold_mb}MB, "
            f"ram_threshold={ram_alert_threshold_mb}MB"
        )

    def _init_db(self):
        """Initialize database table for resource samples."""
        if not self.db_path:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resource_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
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
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource_samples_timestamp
                ON resource_samples(timestamp)
            """)

    def sample(self) -> ResourceSample:
        """Take a point-in-time resource sample."""
        sample = ResourceSample(active_sessions=self._active_sessions)

        # Get RAM info
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            sample.ram_used_mb = int(mem.used / (1024 * 1024))
            sample.ram_available_mb = int(mem.available / (1024 * 1024))
            sample.cpu_percent = psutil.cpu_percent(interval=0.1)

        # Get GPU info
        if HAS_PYNVML:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                sample.vram_used_mb = int(mem_info.used / (1024 * 1024))
                sample.vram_total_mb = int(mem_info.total / (1024 * 1024))
                sample.gpu_utilization_percent = float(util.gpu)
            except Exception as e:
                logger.debug(f"GPU sampling failed: {e}")

        # Check thresholds
        if sample.vram_used_mb > self.vram_threshold:
            sample.alert_triggered = True
            sample.alert_type = "vram_high"
        elif sample.ram_used_mb > self.ram_threshold:
            sample.alert_triggered = True
            sample.alert_type = "ram_high"

        return sample

    def _save_sample(self, sample: ResourceSample):
        """Save sample to database."""
        if not self.db_path:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO resource_samples (
                        timestamp, ram_used_mb, ram_available_mb,
                        vram_used_mb, vram_total_mb, gpu_utilization_percent,
                        cpu_percent, active_sessions, alert_triggered, alert_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sample.timestamp.isoformat(),
                    sample.ram_used_mb,
                    sample.ram_available_mb,
                    sample.vram_used_mb,
                    sample.vram_total_mb,
                    sample.gpu_utilization_percent,
                    sample.cpu_percent,
                    sample.active_sessions,
                    1 if sample.alert_triggered else 0,
                    sample.alert_type,
                ))
        except Exception as e:
            logger.error(f"Failed to save resource sample: {e}")

    def _monitoring_loop(self):
        """Background monitoring loop."""
        while self._running:
            sample = self.sample()

            with self._lock:
                self._samples.append(sample)
                # Keep only last 1000 samples in memory
                if len(self._samples) > 1000:
                    self._samples = self._samples[-1000:]

            self._save_sample(sample)

            if sample.alert_triggered:
                logger.warning(
                    f"Resource alert: {sample.alert_type} - "
                    f"VRAM={sample.vram_used_mb}MB, RAM={sample.ram_used_mb}MB"
                )
                if self.on_alert:
                    try:
                        self.on_alert(sample)
                    except Exception as e:
                        logger.error(f"Alert callback failed: {e}")

            time.sleep(self.sample_interval)

    def start(self):
        """Start background monitoring."""
        if self._running:
            logger.warning("ResourceMonitor already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        logger.info("ResourceMonitor started")

    def stop(self):
        """Stop background monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("ResourceMonitor stopped")

    def set_active_sessions(self, count: int):
        """Update active session count."""
        self._active_sessions = count

    def get_recent_samples(self, count: int = 100) -> List[ResourceSample]:
        """Get recent samples from memory."""
        with self._lock:
            return self._samples[-count:]

    def get_trend(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[ResourceSample]:
        """Get resource trend from database."""
        if not self.db_path:
            return self.get_recent_samples(limit)

        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT * FROM resource_samples"
                params = []

                conditions = []
                if start_time:
                    conditions.append("timestamp >= ?")
                    params.append(start_time.isoformat())
                if end_time:
                    conditions.append("timestamp <= ?")
                    params.append(end_time.isoformat())

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += f" ORDER BY timestamp DESC LIMIT {limit}"

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                samples = []
                for row in rows:
                    samples.append(ResourceSample(
                        timestamp=datetime.fromisoformat(row[1]),
                        ram_used_mb=row[2] or 0,
                        ram_available_mb=row[3] or 0,
                        vram_used_mb=row[4] or 0,
                        vram_total_mb=row[5] or 0,
                        gpu_utilization_percent=row[6] or 0.0,
                        cpu_percent=row[7] or 0.0,
                        active_sessions=row[8] or 0,
                        alert_triggered=bool(row[9]),
                        alert_type=row[10],
                    ))

                return list(reversed(samples))

        except Exception as e:
            logger.error(f"Failed to get resource trend: {e}")
            return []

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> Dict[str, Any]:
        """Get current monitoring stats."""
        current = self.sample()
        return {
            "is_running": self._running,
            "sample_interval_sec": self.sample_interval,
            "samples_in_memory": len(self._samples),
            "current_vram_mb": current.vram_used_mb,
            "current_ram_mb": current.ram_used_mb,
            "vram_threshold_mb": self.vram_threshold,
            "ram_threshold_mb": self.ram_threshold,
            "has_psutil": HAS_PSUTIL,
            "has_pynvml": HAS_PYNVML,
        }


# Global resource monitor instance
_resource_monitor: Optional[ResourceMonitor] = None


def get_resource_monitor(
    db_path: Optional[Path] = None,
    sample_interval_sec: int = 30
) -> ResourceMonitor:
    """Get or create global resource monitor."""
    global _resource_monitor
    if _resource_monitor is None:
        # Load settings from config if available
        try:
            from src.config import settings
            vram_threshold = settings.VRAM_ALERT_THRESHOLD_MB
            ram_threshold = settings.RAM_ALERT_THRESHOLD_MB
            interval = settings.RESOURCE_SAMPLE_INTERVAL_SEC
        except ImportError:
            vram_threshold = 7000
            ram_threshold = 14000
            interval = sample_interval_sec

        _resource_monitor = ResourceMonitor(
            db_path=db_path,
            sample_interval_sec=interval,
            vram_alert_threshold_mb=vram_threshold,
            ram_alert_threshold_mb=ram_threshold,
        )
    return _resource_monitor
