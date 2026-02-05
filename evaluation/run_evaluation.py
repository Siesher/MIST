#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MITS Evaluation Runner

Скрипт для оценки системы по критериям успеха:
1. Socratic Score: ≥0.7 (доля вопросительных ответов)
2. Telling Rate: ≤0.15 (доля прямых ответов)
3. Error Recovery: ≥0.6 (восстановление после ошибок)
4. Session Completion: ≥0.5 (завершённые сессии)
5. Response Latency: <3s p95

T055: Evaluation Script for Success Criteria
"""

import json
import logging
import time
import argparse
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# === Success Criteria ===

SUCCESS_CRITERIA = {
    "socratic_score": {
        "threshold": 0.7,
        "description": "Доля ответов с вопросом (Socratic method)",
        "higher_is_better": True
    },
    "telling_rate": {
        "threshold": 0.15,
        "description": "Доля прямых ответов (нежелательно)",
        "higher_is_better": False
    },
    "error_recovery_rate": {
        "threshold": 0.6,
        "description": "Доля успешных восстановлений после ошибок",
        "higher_is_better": True
    },
    "session_completion_rate": {
        "threshold": 0.5,
        "description": "Доля успешно завершённых сессий",
        "higher_is_better": True
    },
    "response_latency_p95": {
        "threshold": 3000,  # ms
        "description": "95-й перцентиль времени ответа (мс)",
        "higher_is_better": False
    },
    "hint_effectiveness": {
        "threshold": 0.5,
        "description": "Доля подсказок, приведших к прогрессу",
        "higher_is_better": True
    }
}


@dataclass
class EvaluationResult:
    """Result of a single evaluation run."""
    metric_name: str
    value: float
    threshold: float
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    """Complete evaluation report."""
    timestamp: datetime
    total_sessions: int
    total_turns: int
    results: List[EvaluationResult] = field(default_factory=list)
    overall_pass: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_sessions": self.total_sessions,
            "total_turns": self.total_turns,
            "overall_pass": self.overall_pass,
            "metrics": {
                r.metric_name: {
                    "value": r.value,
                    "threshold": r.threshold,
                    "passed": r.passed,
                    "details": r.details
                }
                for r in self.results
            },
            "warnings": self.warnings
        }

    def print_report(self):
        """Print formatted report to console."""
        print("\n" + "=" * 60)
        print("MITS EVALUATION REPORT")
        print("=" * 60)
        print(f"Timestamp: {self.timestamp.isoformat()}")
        print(f"Sessions evaluated: {self.total_sessions}")
        print(f"Total turns: {self.total_turns}")
        print("-" * 60)

        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            direction = "≥" if SUCCESS_CRITERIA[result.metric_name]["higher_is_better"] else "≤"

            print(f"\n{result.metric_name}:")
            print(f"  Value: {result.value:.3f}")
            print(f"  Threshold: {direction} {result.threshold}")
            print(f"  Status: {status}")

            if result.details:
                for key, value in result.details.items():
                    print(f"  {key}: {value}")

        print("\n" + "-" * 60)
        overall_status = "✓ ALL CRITERIA MET" if self.overall_pass else "✗ SOME CRITERIA FAILED"
        print(f"Overall: {overall_status}")

        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")

        print("=" * 60 + "\n")


class MITSEvaluator:
    """
    Evaluator for MITS system performance.

    Measures:
    - Socratic quality (question ratio)
    - Telling rate
    - Error recovery
    - Session completion
    - Response latency
    """

    def __init__(
        self,
        llm_client=None,
        test_data_path: Optional[str] = None
    ):
        """
        Initialize evaluator.

        Args:
            llm_client: LLM client for live evaluation
            test_data_path: Path to test data JSON
        """
        self.llm_client = llm_client
        self.test_data_path = test_data_path
        self.sessions_data: List[Dict] = []
        self.latencies: List[float] = []

    def load_test_data(self, path: str) -> List[Dict]:
        """Load test sessions from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "sessions" in data:
            return data["sessions"]
        else:
            raise ValueError("Invalid test data format")

    def evaluate_session(self, session: Dict) -> Dict[str, Any]:
        """
        Evaluate a single tutoring session.

        Returns metrics for the session.
        """
        turns = session.get("turns", session.get("conversation", []))
        tutor_turns = [t for t in turns if t.get("role") == "tutor"]

        metrics = {
            "turn_count": len(turns),
            "tutor_turn_count": len(tutor_turns),
            "question_count": 0,
            "tell_count": 0,
            "hint_count": 0,
            "scaffold_count": 0,
            "encourage_count": 0,
            "rectify_count": 0,
            "latencies": [],
            "errors_before_recovery": [],
            "completed": session.get("completed", False),
            "success": session.get("success", False)
        }

        # Analyze tutor turns
        for turn in tutor_turns:
            content = turn.get("content", turn.get("message", ""))
            move = turn.get("move", turn.get("move_type", ""))
            latency = turn.get("latency_ms", turn.get("response_time_ms"))

            # Count questions
            if "?" in content:
                metrics["question_count"] += 1

            # Count move types
            if move == "tell":
                metrics["tell_count"] += 1
            elif move == "hint":
                metrics["hint_count"] += 1
            elif move == "scaffolding":
                metrics["scaffold_count"] += 1
            elif move == "encourage":
                metrics["encourage_count"] += 1
            elif move == "rectify":
                metrics["rectify_count"] += 1

            # Track latency
            if latency:
                metrics["latencies"].append(latency)

        return metrics

    def calculate_socratic_score(self, sessions_metrics: List[Dict]) -> float:
        """Calculate Socratic score (question ratio)."""
        total_tutor_turns = sum(m["tutor_turn_count"] for m in sessions_metrics)
        total_questions = sum(m["question_count"] for m in sessions_metrics)

        if total_tutor_turns == 0:
            return 0.0

        return total_questions / total_tutor_turns

    def calculate_telling_rate(self, sessions_metrics: List[Dict]) -> float:
        """Calculate telling rate (direct answer ratio)."""
        total_tutor_turns = sum(m["tutor_turn_count"] for m in sessions_metrics)
        total_tells = sum(m["tell_count"] for m in sessions_metrics)

        if total_tutor_turns == 0:
            return 0.0

        return total_tells / total_tutor_turns

    def calculate_error_recovery_rate(self, sessions_metrics: List[Dict]) -> float:
        """Calculate error recovery rate."""
        # This requires tracking error sequences in sessions
        # Simplified: count sessions with rectify followed by encourage
        recovered = 0
        total_with_errors = 0

        for metrics in sessions_metrics:
            if metrics["rectify_count"] > 0:
                total_with_errors += 1
                if metrics["encourage_count"] > 0 or metrics["success"]:
                    recovered += 1

        if total_with_errors == 0:
            return 1.0  # No errors = perfect recovery

        return recovered / total_with_errors

    def calculate_session_completion_rate(self, sessions_metrics: List[Dict]) -> float:
        """Calculate session completion rate."""
        total = len(sessions_metrics)
        completed = sum(1 for m in sessions_metrics if m.get("completed") or m.get("success"))

        if total == 0:
            return 0.0

        return completed / total

    def calculate_latency_p95(self, sessions_metrics: List[Dict]) -> float:
        """Calculate 95th percentile response latency."""
        all_latencies = []
        for metrics in sessions_metrics:
            all_latencies.extend(metrics.get("latencies", []))

        if not all_latencies:
            return 0.0

        sorted_latencies = sorted(all_latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(p95_index, len(sorted_latencies) - 1)]

    def calculate_hint_effectiveness(self, sessions_metrics: List[Dict]) -> float:
        """Calculate hint effectiveness (hints leading to progress)."""
        # Simplified: ratio of sessions with hints that succeeded
        sessions_with_hints = [m for m in sessions_metrics if m["hint_count"] > 0]

        if not sessions_with_hints:
            return 1.0  # No hints needed = effective teaching

        successful = sum(1 for m in sessions_with_hints if m.get("success"))
        return successful / len(sessions_with_hints)

    def run_evaluation(
        self,
        sessions: Optional[List[Dict]] = None,
        test_data_path: Optional[str] = None
    ) -> EvaluationReport:
        """
        Run full evaluation.

        Args:
            sessions: List of session data (optional)
            test_data_path: Path to test data JSON (optional)

        Returns:
            EvaluationReport with all metrics
        """
        # Load data
        if sessions:
            self.sessions_data = sessions
        elif test_data_path:
            self.sessions_data = self.load_test_data(test_data_path)
        elif self.test_data_path:
            self.sessions_data = self.load_test_data(self.test_data_path)
        else:
            raise ValueError("No test data provided")

        # Evaluate each session
        sessions_metrics = [self.evaluate_session(s) for s in self.sessions_data]

        # Calculate metrics
        results = []

        # 1. Socratic Score
        socratic_score = self.calculate_socratic_score(sessions_metrics)
        results.append(EvaluationResult(
            metric_name="socratic_score",
            value=socratic_score,
            threshold=SUCCESS_CRITERIA["socratic_score"]["threshold"],
            passed=socratic_score >= SUCCESS_CRITERIA["socratic_score"]["threshold"],
            details={
                "question_count": sum(m["question_count"] for m in sessions_metrics),
                "tutor_turns": sum(m["tutor_turn_count"] for m in sessions_metrics)
            }
        ))

        # 2. Telling Rate
        telling_rate = self.calculate_telling_rate(sessions_metrics)
        results.append(EvaluationResult(
            metric_name="telling_rate",
            value=telling_rate,
            threshold=SUCCESS_CRITERIA["telling_rate"]["threshold"],
            passed=telling_rate <= SUCCESS_CRITERIA["telling_rate"]["threshold"],
            details={
                "tell_count": sum(m["tell_count"] for m in sessions_metrics)
            }
        ))

        # 3. Error Recovery Rate
        error_recovery = self.calculate_error_recovery_rate(sessions_metrics)
        results.append(EvaluationResult(
            metric_name="error_recovery_rate",
            value=error_recovery,
            threshold=SUCCESS_CRITERIA["error_recovery_rate"]["threshold"],
            passed=error_recovery >= SUCCESS_CRITERIA["error_recovery_rate"]["threshold"]
        ))

        # 4. Session Completion Rate
        completion_rate = self.calculate_session_completion_rate(sessions_metrics)
        results.append(EvaluationResult(
            metric_name="session_completion_rate",
            value=completion_rate,
            threshold=SUCCESS_CRITERIA["session_completion_rate"]["threshold"],
            passed=completion_rate >= SUCCESS_CRITERIA["session_completion_rate"]["threshold"],
            details={
                "completed": sum(1 for m in sessions_metrics if m.get("completed") or m.get("success")),
                "total": len(sessions_metrics)
            }
        ))

        # 5. Response Latency P95
        latency_p95 = self.calculate_latency_p95(sessions_metrics)
        results.append(EvaluationResult(
            metric_name="response_latency_p95",
            value=latency_p95,
            threshold=SUCCESS_CRITERIA["response_latency_p95"]["threshold"],
            passed=latency_p95 <= SUCCESS_CRITERIA["response_latency_p95"]["threshold"] or latency_p95 == 0
        ))

        # 6. Hint Effectiveness
        hint_effectiveness = self.calculate_hint_effectiveness(sessions_metrics)
        results.append(EvaluationResult(
            metric_name="hint_effectiveness",
            value=hint_effectiveness,
            threshold=SUCCESS_CRITERIA["hint_effectiveness"]["threshold"],
            passed=hint_effectiveness >= SUCCESS_CRITERIA["hint_effectiveness"]["threshold"]
        ))

        # Build report
        total_turns = sum(m["turn_count"] for m in sessions_metrics)
        overall_pass = all(r.passed for r in results)

        report = EvaluationReport(
            timestamp=datetime.now(),
            total_sessions=len(self.sessions_data),
            total_turns=total_turns,
            results=results,
            overall_pass=overall_pass
        )

        # Add warnings
        if telling_rate > 0.1:
            report.warnings.append(f"Telling rate ({telling_rate:.2f}) is higher than recommended")

        if socratic_score < 0.8:
            report.warnings.append(f"Consider increasing question frequency (current: {socratic_score:.2f})")

        return report

    def run_live_evaluation(
        self,
        num_sessions: int = 10,
        tasks_path: str = "data/task_bank.json"
    ) -> EvaluationReport:
        """
        Run live evaluation with actual LLM.

        Args:
            num_sessions: Number of sessions to run
            tasks_path: Path to task bank

        Returns:
            EvaluationReport
        """
        if not self.llm_client:
            raise ValueError("LLM client required for live evaluation")

        from src.agents.orchestrator import AgentOrchestrator, TurnContext

        orchestrator = AgentOrchestrator(
            llm_client=self.llm_client,
            use_rag=True,
            use_knowledge_tracking=True
        )

        # Load tasks
        with open(tasks_path, 'r', encoding='utf-8') as f:
            tasks = json.load(f)

        sessions = []
        for i in range(min(num_sessions, len(tasks))):
            task = tasks[i]
            session = self._run_simulated_session(orchestrator, task)
            sessions.append(session)

        return self.run_evaluation(sessions=sessions)

    def _run_simulated_session(
        self,
        orchestrator,
        task: Dict
    ) -> Dict:
        """Run a simulated tutoring session."""
        from src.agents.orchestrator import TurnContext

        session = {
            "task": task,
            "turns": [],
            "completed": False,
            "success": False
        }

        # Simulated student responses
        student_messages = [
            "Не знаю как начать",
            "Может быть попробовать разложить?",
            "Получается (x-2)(x-3)=0?",
            "Значит x=2 или x=3!"
        ]

        for msg in student_messages:
            start_time = time.time()

            context = TurnContext(
                problem=task.get("problem", ""),
                student_input=msg,
                correct_answer=task.get("answer", ""),
                topic=task.get("topic")
            )

            result = orchestrator.process_turn(context)
            latency = (time.time() - start_time) * 1000

            session["turns"].append({
                "role": "student",
                "content": msg
            })

            session["turns"].append({
                "role": "tutor",
                "content": result.response,
                "move": result.move_type,
                "latency_ms": latency
            })

            # Check for completion
            if result.move_type == "encourage" and "отлично" in result.response.lower():
                session["completed"] = True
                session["success"] = True
                break

        return session


def main():
    """Main entry point for evaluation script."""
    parser = argparse.ArgumentParser(description="MITS Evaluation Runner")
    parser.add_argument(
        "--data",
        type=str,
        help="Path to test data JSON file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation/results/eval_report.json",
        help="Output path for evaluation report"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live evaluation with actual LLM"
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=10,
        help="Number of sessions for live evaluation"
    )

    args = parser.parse_args()

    evaluator = MITSEvaluator()

    if args.live:
        print("Live evaluation not implemented without LLM client")
        print("Use --data to evaluate pre-recorded sessions")
        return

    if args.data:
        report = evaluator.run_evaluation(test_data_path=args.data)
    else:
        # Generate sample data for demo
        sample_sessions = generate_sample_sessions()
        report = evaluator.run_evaluation(sessions=sample_sessions)

    # Print report
    report.print_report()

    # Save report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"Report saved to: {output_path}")

    # Exit with status
    sys.exit(0 if report.overall_pass else 1)


def generate_sample_sessions() -> List[Dict]:
    """Generate sample sessions for demo evaluation."""
    return [
        {
            "id": "sample-1",
            "completed": True,
            "success": True,
            "turns": [
                {"role": "student", "content": "Не знаю как решить x^2 - 5x + 6 = 0"},
                {"role": "tutor", "content": "Какие методы решения квадратных уравнений ты знаешь?", "move": "scaffolding", "latency_ms": 500},
                {"role": "student", "content": "Можно разложить на множители?"},
                {"role": "tutor", "content": "Отлично! Какие два числа дают в сумме -5, а в произведении 6?", "move": "scaffolding", "latency_ms": 450},
                {"role": "student", "content": "-2 и -3"},
                {"role": "tutor", "content": "Верно! Значит уравнение можно записать как...?", "move": "encourage", "latency_ms": 400},
                {"role": "student", "content": "(x-2)(x-3) = 0, значит x=2 или x=3"},
                {"role": "tutor", "content": "Отлично! Ты нашёл правильный ответ!", "move": "encourage", "latency_ms": 350},
            ]
        },
        {
            "id": "sample-2",
            "completed": True,
            "success": True,
            "turns": [
                {"role": "student", "content": "Как найти производную sin(x)?"},
                {"role": "tutor", "content": "Помнишь таблицу производных? Что там написано про sin?", "move": "scaffolding", "latency_ms": 520},
                {"role": "student", "content": "cos(x)?"},
                {"role": "tutor", "content": "Точно! (sin x)' = cos x. Молодец!", "move": "encourage", "latency_ms": 380},
            ]
        },
        {
            "id": "sample-3",
            "completed": False,
            "success": False,
            "turns": [
                {"role": "student", "content": "Не понимаю интегралы"},
                {"role": "tutor", "content": "Интеграл - это операция, обратная дифференцированию. С какой функции начнём?", "move": "scaffolding", "latency_ms": 600},
                {"role": "student", "content": "Сдаюсь"},
                {"role": "tutor", "content": "Давай попробуем с простого примера. Какова производная x^2?", "move": "hint", "latency_ms": 450},
            ]
        },
        {
            "id": "sample-4",
            "completed": True,
            "success": True,
            "turns": [
                {"role": "student", "content": "3 + 5 * 2 = ?"},
                {"role": "tutor", "content": "Какой порядок операций нужно соблюдать?", "move": "scaffolding", "latency_ms": 300},
                {"role": "student", "content": "Сначала умножение: 5*2=10, потом 3+10=13"},
                {"role": "tutor", "content": "Отлично! Правильно!", "move": "encourage", "latency_ms": 280},
            ]
        },
        {
            "id": "sample-5",
            "completed": True,
            "success": True,
            "turns": [
                {"role": "student", "content": "Что такое дискриминант?"},
                {"role": "tutor", "content": "Дискриминант - это выражение, которое определяет количество корней. Как его вычислить?", "move": "scaffolding", "latency_ms": 550},
                {"role": "student", "content": "D = b^2 - 4ac"},
                {"role": "tutor", "content": "Верно! И что показывает знак D?", "move": "encourage", "latency_ms": 400},
                {"role": "student", "content": "Если D>0 - два корня, D=0 - один, D<0 - нет"},
                {"role": "tutor", "content": "Отлично! Ты хорошо понял!", "move": "encourage", "latency_ms": 350},
            ]
        }
    ]


if __name__ == "__main__":
    main()
