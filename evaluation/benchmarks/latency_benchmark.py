"""
Latency Benchmark

Measures response time per mode (chat, guided_learning, task_generator).

Metrics:
- P50/P90/P99 response times per mode
- Average response time
- Cache hit rate and speedup

Usage:
    python -m evaluation.benchmarks.latency_benchmark \
        --backend-url http://localhost:8000 \
        --output evaluation/reports/latency.json \
        --requests-per-mode 20
"""

import json
import time
import logging
import argparse
import statistics
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

MODES = ["chat", "guided_learning", "task_generator"]

TEST_MESSAGES = {
    "chat": [
        "Привет, объясни что такое производная",
        "Как найти производную x^2?",
        "Что такое предел функции?",
        "Расскажи про интегралы",
        "Как решить квадратное уравнение?",
    ],
    "guided_learning": [
        "Я хочу изучить производные",
        "Начнём тему пределов",
        "Давай разберём интегрирование",
        "Помоги с тригонометрией",
        "Объясни линейную алгебру",
    ],
    "task_generator": [
        "Дай задачу на производные",
        "Задача на интегралы",
        "Придумай задачу на пределы",
        "Задача на уравнения",
        "Сгенерируй задачу по тригонометрии",
    ],
}


@dataclass
class ModeLatency:
    """Latency statistics for a single mode."""
    mode: str = ""
    requests: int = 0
    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    errors: int = 0


@dataclass
class LatencyResult:
    """Full latency benchmark result."""
    total_requests: int = 0
    total_errors: int = 0
    overall_avg_ms: float = 0.0
    by_mode: List[Dict[str, Any]] = field(default_factory=list)


def percentile(data: List[float], p: float) -> float:
    """Compute percentile."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def measure_request(backend_url: str, session_id: str, message: str, mode: str) -> float:
    """Send a request and measure response time in ms."""
    import requests

    url = f"{backend_url}/api/v1/chat/{session_id}/message"
    payload = {"message": message, "mode": mode}

    start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Request failed: {e}")
        return -1.0

    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms


def create_session(backend_url: str, mode: str) -> str:
    """Create a test session."""
    import requests

    url = f"{backend_url}/api/v1/sessions"
    payload = {"topic": "test_benchmark", "mode": mode}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json().get("session_id", "")
    except Exception:
        return ""


def run_benchmark(backend_url: str, requests_per_mode: int = 20) -> LatencyResult:
    """Run latency benchmark against live backend."""
    result = LatencyResult()
    all_times = []

    for mode in MODES:
        session_id = create_session(backend_url, mode)
        if not session_id:
            logger.error(f"Failed to create session for mode={mode}")
            continue

        times = []
        messages = TEST_MESSAGES.get(mode, TEST_MESSAGES["chat"])
        errors = 0

        for i in range(requests_per_mode):
            msg = messages[i % len(messages)]
            elapsed = measure_request(backend_url, session_id, msg, mode)

            if elapsed < 0:
                errors += 1
            else:
                times.append(elapsed)
                all_times.append(elapsed)

        mode_result = ModeLatency(
            mode=mode,
            requests=requests_per_mode,
            avg_ms=statistics.mean(times) if times else 0,
            p50_ms=percentile(times, 50),
            p90_ms=percentile(times, 90),
            p99_ms=percentile(times, 99),
            min_ms=min(times) if times else 0,
            max_ms=max(times) if times else 0,
            errors=errors,
        )
        result.by_mode.append(asdict(mode_result))
        result.total_requests += requests_per_mode
        result.total_errors += errors

        logger.info(f"Mode {mode}: avg={mode_result.avg_ms:.0f}ms, p90={mode_result.p90_ms:.0f}ms")

    if all_times:
        result.overall_avg_ms = statistics.mean(all_times)

    return result


def main():
    parser = argparse.ArgumentParser(description="Latency benchmark")
    parser.add_argument("--backend-url", type=str, default="http://localhost:8000")
    parser.add_argument("--output", type=str, default="evaluation/reports/latency.json")
    parser.add_argument("--requests-per-mode", type=int, default=20)
    args = parser.parse_args()

    result = run_benchmark(args.backend_url, args.requests_per_mode)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)

    print(f"\nOverall avg latency: {result.overall_avg_ms:.0f}ms")
    print(f"Total requests: {result.total_requests}")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
