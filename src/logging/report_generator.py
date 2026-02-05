"""
Report Generator for MITS.

Feature 010: Automatic report generation with matplotlib charts
for diploma defense.

Generates:
- Daily/weekly metrics reports
- Performance charts (response time, cache hit rate, VRAM)
- A/B test results visualization
- Export to JSON, CSV, PNG
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Try to import visualization libraries
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    plt = None
    logger.warning("matplotlib not available - chart generation disabled")

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    sns = None

# Load configuration
try:
    from src.config import settings
    REPORTS_PATH = getattr(settings, 'REPORTS_PATH', Path('./data/reports'))
    METRICS_DB_PATH = getattr(settings, 'METRICS_DB_PATH', Path('./data/metrics.db'))
except ImportError:
    REPORTS_PATH = Path('./data/reports')
    METRICS_DB_PATH = Path('./data/metrics.db')


@dataclass
class ChartConfig:
    """Configuration for chart generation."""
    width: int = 10
    height: int = 6
    dpi: int = 100
    style: str = "seaborn-v0_8-whitegrid"
    title_fontsize: int = 14
    label_fontsize: int = 12
    legend_fontsize: int = 10


@dataclass
class ReportData:
    """Aggregated data for report generation."""
    period_start: datetime
    period_end: datetime
    total_sessions: int = 0
    sessions_solved: int = 0
    sessions_told: int = 0

    # Performance metrics
    avg_response_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    avg_tokens_per_session: float = 0.0
    avg_vram_mb: float = 0.0
    avg_ram_mb: float = 0.0

    # Quality metrics
    avg_hints_per_session: float = 0.0
    avg_attempts_per_session: float = 0.0
    avg_duration_seconds: float = 0.0

    # Feature usage
    few_shot_usage_rate: float = 0.0
    cot_usage_rate: float = 0.0
    avg_compression_ratio: float = 1.0

    # A/B test data
    ab_variants: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Time series data
    daily_metrics: List[Dict[str, Any]] = field(default_factory=list)

    # Topic breakdown
    topics_breakdown: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_sessions": self.total_sessions,
            "sessions_solved": self.sessions_solved,
            "sessions_told": self.sessions_told,
            "success_rate": self.sessions_solved / self.total_sessions if self.total_sessions > 0 else 0,
            "telling_rate": self.sessions_told / self.total_sessions if self.total_sessions > 0 else 0,
            "performance": {
                "avg_response_time_ms": self.avg_response_time_ms,
                "cache_hit_rate": self.cache_hit_rate,
                "avg_tokens_per_session": self.avg_tokens_per_session,
                "avg_vram_mb": self.avg_vram_mb,
                "avg_ram_mb": self.avg_ram_mb,
            },
            "quality": {
                "avg_hints_per_session": self.avg_hints_per_session,
                "avg_attempts_per_session": self.avg_attempts_per_session,
                "avg_duration_seconds": self.avg_duration_seconds,
            },
            "features": {
                "few_shot_usage_rate": self.few_shot_usage_rate,
                "cot_usage_rate": self.cot_usage_rate,
                "avg_compression_ratio": self.avg_compression_ratio,
            },
            "ab_variants": self.ab_variants,
            "daily_metrics": self.daily_metrics,
            "topics_breakdown": self.topics_breakdown,
        }


class ReportGenerator:
    """
    Generates performance reports with charts for diploma defense.

    Supports:
    - Daily and weekly aggregation
    - Response time analysis
    - Cache efficiency metrics
    - A/B test visualization
    - Resource usage tracking
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        chart_config: Optional[ChartConfig] = None
    ):
        self.db_path = db_path or METRICS_DB_PATH
        self.output_path = output_path or REPORTS_PATH
        self.chart_config = chart_config or ChartConfig()

        # Ensure output directory exists
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Setup matplotlib style
        if HAS_MATPLOTLIB:
            try:
                plt.style.use(self.chart_config.style)
            except Exception:
                plt.style.use('default')

        logger.info(f"ReportGenerator initialized: output={self.output_path}")

    def aggregate_data(
        self,
        days: int = 7,
        end_date: Optional[datetime] = None
    ) -> ReportData:
        """
        Aggregate metrics data for report.

        Args:
            days: Number of days to aggregate
            end_date: End date (default: now)

        Returns:
            ReportData with aggregated metrics
        """
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=days)

        report = ReportData(
            period_start=start_date,
            period_end=end_date
        )

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Aggregate session metrics
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(is_solved) as solved,
                    SUM(told_answer) as told,
                    AVG(avg_response_time_ms) as avg_response_time,
                    SUM(cache_hits) as cache_hits,
                    SUM(cache_misses) as cache_misses,
                    AVG(total_tokens_used) as avg_tokens,
                    AVG(peak_vram_mb) as avg_vram,
                    AVG(peak_ram_mb) as avg_ram,
                    AVG(hints_used) as avg_hints,
                    AVG(attempts) as avg_attempts,
                    AVG(duration_seconds) as avg_duration,
                    SUM(few_shot_used) as few_shot_count,
                    SUM(cot_used) as cot_count,
                    AVG(compression_ratio) as avg_compression
                FROM sessions
                WHERE start_time >= ? AND start_time <= ?
            """, (start_date.isoformat(), end_date.isoformat()))

            row = cursor.fetchone()
            if row and row[0]:
                total = row[0]
                cache_total = (row[4] or 0) + (row[5] or 0)

                report.total_sessions = total
                report.sessions_solved = row[1] or 0
                report.sessions_told = row[2] or 0
                report.avg_response_time_ms = row[3] or 0
                report.cache_hit_rate = (row[4] or 0) / cache_total if cache_total > 0 else 0
                report.avg_tokens_per_session = row[6] or 0
                report.avg_vram_mb = row[7] or 0
                report.avg_ram_mb = row[8] or 0
                report.avg_hints_per_session = row[9] or 0
                report.avg_attempts_per_session = row[10] or 0
                report.avg_duration_seconds = row[11] or 0
                report.few_shot_usage_rate = (row[12] or 0) / total if total > 0 else 0
                report.cot_usage_rate = (row[13] or 0) / total if total > 0 else 0
                report.avg_compression_ratio = row[14] or 1.0

            # Get daily breakdown
            cursor.execute("""
                SELECT
                    date(start_time) as day,
                    COUNT(*) as total,
                    SUM(is_solved) as solved,
                    AVG(avg_response_time_ms) as avg_response_time,
                    SUM(cache_hits) as cache_hits,
                    SUM(cache_misses) as cache_misses
                FROM sessions
                WHERE start_time >= ? AND start_time <= ?
                GROUP BY date(start_time)
                ORDER BY day
            """, (start_date.isoformat(), end_date.isoformat()))

            for row in cursor.fetchall():
                cache_total = (row[4] or 0) + (row[5] or 0)
                report.daily_metrics.append({
                    "date": row[0],
                    "total_sessions": row[1],
                    "sessions_solved": row[2] or 0,
                    "avg_response_time_ms": row[3] or 0,
                    "cache_hit_rate": (row[4] or 0) / cache_total if cache_total > 0 else 0,
                })

            # Get topic breakdown
            cursor.execute("""
                SELECT task_topic, COUNT(*) as count
                FROM sessions
                WHERE start_time >= ? AND start_time <= ?
                GROUP BY task_topic
                ORDER BY count DESC
            """, (start_date.isoformat(), end_date.isoformat()))

            for row in cursor.fetchall():
                if row[0]:
                    report.topics_breakdown[row[0]] = row[1]

            # Get A/B variant data
            cursor.execute("""
                SELECT
                    ab_variant,
                    COUNT(*) as total,
                    SUM(is_solved) as solved,
                    AVG(avg_response_time_ms) as avg_response_time,
                    AVG(hints_used) as avg_hints
                FROM sessions
                WHERE start_time >= ? AND start_time <= ?
                  AND ab_variant IS NOT NULL
                GROUP BY ab_variant
            """, (start_date.isoformat(), end_date.isoformat()))

            for row in cursor.fetchall():
                if row[0]:
                    report.ab_variants[row[0]] = {
                        "total_sessions": row[1],
                        "sessions_solved": row[2] or 0,
                        "success_rate": (row[2] or 0) / row[1] if row[1] > 0 else 0,
                        "avg_response_time_ms": row[3] or 0,
                        "avg_hints": row[4] or 0,
                    }

        except sqlite3.OperationalError as e:
            logger.warning(f"Database query error: {e}")
        finally:
            conn.close()

        return report

    def generate_response_time_chart(
        self,
        data: ReportData,
        filename: str = "response_time.png"
    ) -> Optional[Path]:
        """Generate response time over time chart."""
        if not HAS_MATPLOTLIB or not data.daily_metrics:
            return None

        fig, ax = plt.subplots(
            figsize=(self.chart_config.width, self.chart_config.height),
            dpi=self.chart_config.dpi
        )

        dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in data.daily_metrics]
        response_times = [d["avg_response_time_ms"] for d in data.daily_metrics]

        ax.plot(dates, response_times, marker='o', linewidth=2, markersize=6)
        ax.axhline(y=2000, color='r', linestyle='--', label='Целевое время (2000 мс)')

        ax.set_xlabel('Дата', fontsize=self.chart_config.label_fontsize)
        ax.set_ylabel('Среднее время ответа (мс)', fontsize=self.chart_config.label_fontsize)
        ax.set_title('Время ответа системы', fontsize=self.chart_config.title_fontsize)
        ax.legend(fontsize=self.chart_config.legend_fontsize)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator())
        plt.xticks(rotation=45)

        plt.tight_layout()

        output_file = self.output_path / filename
        plt.savefig(output_file)
        plt.close()

        logger.info(f"Response time chart saved: {output_file}")
        return output_file

    def generate_cache_efficiency_chart(
        self,
        data: ReportData,
        filename: str = "cache_efficiency.png"
    ) -> Optional[Path]:
        """Generate cache hit rate chart."""
        if not HAS_MATPLOTLIB or not data.daily_metrics:
            return None

        fig, ax = plt.subplots(
            figsize=(self.chart_config.width, self.chart_config.height),
            dpi=self.chart_config.dpi
        )

        dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in data.daily_metrics]
        hit_rates = [d["cache_hit_rate"] * 100 for d in data.daily_metrics]

        ax.bar(dates, hit_rates, color='steelblue', alpha=0.8)
        ax.axhline(y=20, color='g', linestyle='--', label='Целевой показатель (20%)')

        ax.set_xlabel('Дата', fontsize=self.chart_config.label_fontsize)
        ax.set_ylabel('Cache Hit Rate (%)', fontsize=self.chart_config.label_fontsize)
        ax.set_title('Эффективность кэширования', fontsize=self.chart_config.title_fontsize)
        ax.legend(fontsize=self.chart_config.legend_fontsize)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        plt.xticks(rotation=45)

        plt.tight_layout()

        output_file = self.output_path / filename
        plt.savefig(output_file)
        plt.close()

        logger.info(f"Cache efficiency chart saved: {output_file}")
        return output_file

    def generate_success_rate_chart(
        self,
        data: ReportData,
        filename: str = "success_rate.png"
    ) -> Optional[Path]:
        """Generate session success rate chart."""
        if not HAS_MATPLOTLIB or not data.daily_metrics:
            return None

        fig, ax = plt.subplots(
            figsize=(self.chart_config.width, self.chart_config.height),
            dpi=self.chart_config.dpi
        )

        dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in data.daily_metrics]
        success_rates = [
            (d["sessions_solved"] / d["total_sessions"] * 100) if d["total_sessions"] > 0 else 0
            for d in data.daily_metrics
        ]

        ax.fill_between(dates, success_rates, alpha=0.3)
        ax.plot(dates, success_rates, marker='o', linewidth=2, markersize=6)

        ax.set_xlabel('Дата', fontsize=self.chart_config.label_fontsize)
        ax.set_ylabel('Успешность (%)', fontsize=self.chart_config.label_fontsize)
        ax.set_title('Успешность решения задач', fontsize=self.chart_config.title_fontsize)
        ax.set_ylim(0, 100)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        plt.xticks(rotation=45)

        plt.tight_layout()

        output_file = self.output_path / filename
        plt.savefig(output_file)
        plt.close()

        logger.info(f"Success rate chart saved: {output_file}")
        return output_file

    def generate_ab_comparison_chart(
        self,
        data: ReportData,
        filename: str = "ab_comparison.png"
    ) -> Optional[Path]:
        """Generate A/B test comparison chart."""
        if not HAS_MATPLOTLIB or not data.ab_variants:
            return None

        fig, axes = plt.subplots(
            1, 3,
            figsize=(self.chart_config.width * 1.5, self.chart_config.height),
            dpi=self.chart_config.dpi
        )

        variants = list(data.ab_variants.keys())

        # Success rate comparison
        success_rates = [data.ab_variants[v]["success_rate"] * 100 for v in variants]
        axes[0].bar(variants, success_rates, color=['steelblue', 'coral'][:len(variants)])
        axes[0].set_ylabel('Успешность (%)')
        axes[0].set_title('Успешность по вариантам')

        # Response time comparison
        response_times = [data.ab_variants[v]["avg_response_time_ms"] for v in variants]
        axes[1].bar(variants, response_times, color=['steelblue', 'coral'][:len(variants)])
        axes[1].set_ylabel('Время ответа (мс)')
        axes[1].set_title('Время ответа по вариантам')

        # Hints usage comparison
        hints = [data.ab_variants[v]["avg_hints"] for v in variants]
        axes[2].bar(variants, hints, color=['steelblue', 'coral'][:len(variants)])
        axes[2].set_ylabel('Среднее кол-во подсказок')
        axes[2].set_title('Подсказки по вариантам')

        plt.suptitle('Сравнение A/B вариантов', fontsize=self.chart_config.title_fontsize)
        plt.tight_layout()

        output_file = self.output_path / filename
        plt.savefig(output_file)
        plt.close()

        logger.info(f"A/B comparison chart saved: {output_file}")
        return output_file

    def generate_topics_chart(
        self,
        data: ReportData,
        filename: str = "topics_breakdown.png"
    ) -> Optional[Path]:
        """Generate topic distribution pie chart."""
        if not HAS_MATPLOTLIB or not data.topics_breakdown:
            return None

        fig, ax = plt.subplots(
            figsize=(self.chart_config.height, self.chart_config.height),
            dpi=self.chart_config.dpi
        )

        # Get top 8 topics, group rest as "Другие"
        sorted_topics = sorted(
            data.topics_breakdown.items(),
            key=lambda x: x[1],
            reverse=True
        )

        if len(sorted_topics) > 8:
            top_topics = dict(sorted_topics[:7])
            other_count = sum(v for k, v in sorted_topics[7:])
            top_topics["Другие"] = other_count
        else:
            top_topics = dict(sorted_topics)

        ax.pie(
            top_topics.values(),
            labels=top_topics.keys(),
            autopct='%1.1f%%',
            startangle=90
        )
        ax.set_title('Распределение по темам', fontsize=self.chart_config.title_fontsize)

        plt.tight_layout()

        output_file = self.output_path / filename
        plt.savefig(output_file)
        plt.close()

        logger.info(f"Topics chart saved: {output_file}")
        return output_file

    def generate_summary_dashboard(
        self,
        data: ReportData,
        filename: str = "dashboard.png"
    ) -> Optional[Path]:
        """Generate summary dashboard with key metrics."""
        if not HAS_MATPLOTLIB:
            return None

        fig = plt.figure(
            figsize=(self.chart_config.width * 1.5, self.chart_config.height * 1.5),
            dpi=self.chart_config.dpi
        )

        # Create grid
        gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)

        # Key metrics text box
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.axis('off')

        success_rate = data.sessions_solved / data.total_sessions * 100 if data.total_sessions > 0 else 0
        telling_rate = data.sessions_told / data.total_sessions * 100 if data.total_sessions > 0 else 0

        metrics_text = f"""Ключевые метрики
─────────────────────
Всего сессий: {data.total_sessions}
Успешность: {success_rate:.1f}%
Подсказки (tell): {telling_rate:.1f}%
─────────────────────
Время ответа: {data.avg_response_time_ms:.0f} мс
Cache Hit Rate: {data.cache_hit_rate*100:.1f}%
VRAM: {data.avg_vram_mb:.0f} MB
─────────────────────
Few-shot: {data.few_shot_usage_rate*100:.1f}%
CoT: {data.cot_usage_rate*100:.1f}%"""

        ax1.text(0.1, 0.9, metrics_text, transform=ax1.transAxes,
                 fontsize=10, verticalalignment='top', family='monospace',
                 bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # Response time trend
        ax2 = fig.add_subplot(gs[0, 1:])
        if data.daily_metrics:
            dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in data.daily_metrics]
            response_times = [d["avg_response_time_ms"] for d in data.daily_metrics]
            ax2.plot(dates, response_times, marker='o', linewidth=2)
            ax2.axhline(y=2000, color='r', linestyle='--', alpha=0.7)
            ax2.set_ylabel('Время ответа (мс)')
            ax2.set_title('Динамика времени ответа')
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        # Cache efficiency
        ax3 = fig.add_subplot(gs[1, 0])
        if data.daily_metrics:
            dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in data.daily_metrics]
            hit_rates = [d["cache_hit_rate"] * 100 for d in data.daily_metrics]
            ax3.bar(dates, hit_rates, alpha=0.8)
            ax3.set_ylabel('Cache Hit (%)')
            ax3.set_title('Кэширование')
            ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

        # Success rate
        ax4 = fig.add_subplot(gs[1, 1])
        if data.daily_metrics:
            dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in data.daily_metrics]
            success_rates = [
                (d["sessions_solved"] / d["total_sessions"] * 100) if d["total_sessions"] > 0 else 0
                for d in data.daily_metrics
            ]
            ax4.fill_between(dates, success_rates, alpha=0.3)
            ax4.plot(dates, success_rates, marker='o')
            ax4.set_ylabel('Успешность (%)')
            ax4.set_title('Успешность')
            ax4.set_ylim(0, 100)
            ax4.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)

        # Topics pie
        ax5 = fig.add_subplot(gs[1, 2])
        if data.topics_breakdown:
            sorted_topics = sorted(data.topics_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]
            topics = dict(sorted_topics)
            ax5.pie(topics.values(), labels=topics.keys(), autopct='%1.0f%%')
            ax5.set_title('Топ-5 тем')

        # Title
        period_str = f"{data.period_start.strftime('%d.%m.%Y')} - {data.period_end.strftime('%d.%m.%Y')}"
        fig.suptitle(f'MITS Performance Dashboard ({period_str})', fontsize=14, fontweight='bold')

        output_file = self.output_path / filename
        plt.savefig(output_file, bbox_inches='tight')
        plt.close()

        logger.info(f"Dashboard saved: {output_file}")
        return output_file

    def export_json(
        self,
        data: ReportData,
        filename: str = "report.json"
    ) -> Path:
        """Export report data to JSON."""
        output_file = self.output_path / filename

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"JSON report saved: {output_file}")
        return output_file

    def export_csv(
        self,
        data: ReportData,
        filename: str = "report.csv"
    ) -> Path:
        """Export daily metrics to CSV."""
        output_file = self.output_path / filename

        with open(output_file, 'w', encoding='utf-8') as f:
            # Header
            f.write("date,total_sessions,sessions_solved,success_rate,avg_response_time_ms,cache_hit_rate\n")

            # Data rows
            for day in data.daily_metrics:
                success_rate = (day["sessions_solved"] / day["total_sessions"] * 100) if day["total_sessions"] > 0 else 0
                f.write(f"{day['date']},{day['total_sessions']},{day['sessions_solved']},{success_rate:.2f},{day['avg_response_time_ms']:.2f},{day['cache_hit_rate']:.4f}\n")

        logger.info(f"CSV report saved: {output_file}")
        return output_file

    def generate_full_report(
        self,
        days: int = 7,
        prefix: str = ""
    ) -> Dict[str, Path]:
        """
        Generate complete report with all charts and exports.

        Args:
            days: Number of days to include
            prefix: Filename prefix (e.g., "weekly_" or "daily_")

        Returns:
            Dictionary of generated file paths
        """
        logger.info(f"Generating full report for {days} days")

        # Aggregate data
        data = self.aggregate_data(days=days)

        if data.total_sessions == 0:
            logger.warning("No data available for report generation")
            return {}

        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        files = {}

        # Generate all charts
        chart_methods = [
            ("response_time", self.generate_response_time_chart),
            ("cache_efficiency", self.generate_cache_efficiency_chart),
            ("success_rate", self.generate_success_rate_chart),
            ("ab_comparison", self.generate_ab_comparison_chart),
            ("topics", self.generate_topics_chart),
            ("dashboard", self.generate_summary_dashboard),
        ]

        for name, method in chart_methods:
            try:
                filename = f"{prefix}{name}_{timestamp}.png"
                result = method(data, filename)
                if result:
                    files[name] = result
            except Exception as e:
                logger.error(f"Failed to generate {name} chart: {e}")

        # Export data
        try:
            files["json"] = self.export_json(data, f"{prefix}report_{timestamp}.json")
            files["csv"] = self.export_csv(data, f"{prefix}metrics_{timestamp}.csv")
        except Exception as e:
            logger.error(f"Failed to export data: {e}")

        logger.info(f"Full report generated: {len(files)} files")
        return files


# Global instance
_report_generator: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """Get or create global report generator."""
    global _report_generator
    if _report_generator is None:
        _report_generator = ReportGenerator()
    return _report_generator


def generate_daily_report() -> Dict[str, Path]:
    """Generate daily report."""
    return get_report_generator().generate_full_report(days=1, prefix="daily_")


def generate_weekly_report() -> Dict[str, Path]:
    """Generate weekly report."""
    return get_report_generator().generate_full_report(days=7, prefix="weekly_")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Report Generator Demo ===\n")

    generator = ReportGenerator()

    # Try to generate sample report
    data = generator.aggregate_data(days=7)

    if data.total_sessions > 0:
        files = generator.generate_full_report(days=7, prefix="demo_")
        print(f"\nGenerated {len(files)} report files:")
        for name, path in files.items():
            print(f"  - {name}: {path}")
    else:
        print("No session data available for report generation.")
        print("Run some tutoring sessions first.")
