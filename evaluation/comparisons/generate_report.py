"""
Report Generator for Thesis

Formats benchmark results as markdown tables suitable for diploma thesis.

Usage:
    python -m evaluation.comparisons.generate_report \
        --results evaluation/reports/benchmark_results.json \
        --output evaluation/reports/thesis_tables.md
"""

import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def format_model_comparison(data: dict) -> str:
    base = data.get("base", data.get("base_model", {}))
    ft = data.get("finetuned", data.get("finetuned_model", {}))
    lines = [
        "### Таблица 1. Сравнение базовой и дообученной модели",
        "",
        "| Метрика | Базовая модель | Дообученная модель | Δ |",
        "|---------|---------------:|-------------------:|--:|",
    ]
    for label, key in [("Socratic Score", "socratic_score"), ("Telling Rate", "telling_rate"),
                       ("Ср. время ответа (мс)", "avg_latency_ms"), ("Ср. длина ответа", "avg_response_length")]:
        b = base.get(key, 0)
        f = ft.get(key, 0)
        delta = f - b
        fmt = ".3f" if isinstance(b, float) and b < 10 else ".0f"
        lines.append(f"| {label} | {b:{fmt}} | {f:{fmt}} | {delta:+{fmt}} |")
    lines.append("")
    return "\n".join(lines)


def format_knowledge_comparison(data: dict) -> str:
    bkt = data.get("bkt", data.get("bkt_metrics", {}))
    dkt = data.get("dkt", data.get("dkt_metrics", {}))
    lines = [
        "### Таблица 2. Сравнение моделей отслеживания знаний",
        "",
        "| Метрика | BKT | DKT (LSTM) | Δ |",
        "|---------|----:|-----------:|--:|",
    ]
    for label, key in [("AUC", "auc"), ("RMSE", "rmse"), ("Accuracy", "accuracy")]:
        b = bkt.get(key, 0)
        d = dkt.get(key, 0)
        delta = (b - d) if key == "rmse" else (d - b)
        lines.append(f"| {label} | {b:.4f} | {d:.4f} | {delta:+.4f} |")
    lines.append("")
    return "\n".join(lines)


def format_affect_comparison(data: dict) -> str:
    rules = data.get("rules", data.get("rules_metrics", {}))
    ml = data.get("ml", data.get("ml_metrics", {}))
    lines = [
        "### Таблица 3. Сравнение детекторов аффективного состояния",
        "",
        "| Метрика | Rule-based | ML (RuBERT) | Δ |",
        "|---------|----------:|------------:|--:|",
    ]
    for label, key in [("Macro F1", "macro_f1"), ("Accuracy", "accuracy")]:
        r = rules.get(key, 0)
        m = ml.get(key, 0)
        lines.append(f"| {label} | {r:.4f} | {m:.4f} | {m - r:+.4f} |")

    lines.extend(["", "#### Метрики по классам (ML детектор)", "",
                   "| Класс | Precision | Recall | F1 | Support |",
                   "|-------|----------:|-------:|---:|--------:|"])
    for cls in ml.get("per_class", []):
        lines.append(f"| {cls['label']} | {cls['precision']:.3f} | {cls['recall']:.3f} | {cls['f1']:.3f} | {cls['support']} |")
    lines.append("")
    return "\n".join(lines)


def format_socratic_results(data: dict) -> str:
    return "\n".join([
        "### Таблица 4. Результаты Сократического анализа", "",
        "| Метрика | Значение |", "|---------|--------:|",
        f"| Socratic Score | {data.get('socratic_score', 0):.3f} |",
        f"| Telling Rate | {data.get('telling_rate', 0):.3f} |",
        f"| Всего реплик тьютора | {data.get('total_tutor_turns', 0)} |",
        f"| Направляющих | {data.get('guiding_turns', 0)} |",
        f"| Прямых ответов | {data.get('telling_turns', 0)} |", "",
    ])


def generate_thesis_report(results: dict) -> str:
    sections = [
        "# Результаты экспериментальной оценки MITS", "",
        f"Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "", "---", "",
    ]
    if "base_vs_finetuned" in results and "error" not in results["base_vs_finetuned"]:
        sections.append(format_model_comparison(results["base_vs_finetuned"]))
    if "knowledge_prediction" in results and "error" not in results["knowledge_prediction"]:
        sections.append(format_knowledge_comparison(results["knowledge_prediction"]))
    if "affect_accuracy" in results and "error" not in results["affect_accuracy"]:
        sections.append(format_affect_comparison(results["affect_accuracy"]))
    if "socratic_score" in results and "error" not in results["socratic_score"]:
        sections.append(format_socratic_results(results["socratic_score"]))
    if "error_recovery" in results and "error" not in results["error_recovery"]:
        er = results["error_recovery"]
        sections.extend([
            "### Таблица 5. Восстановление после ошибок", "",
            "| Метрика | Значение |", "|---------|--------:|",
            f"| Recovery Rate | {er.get('recovery_rate', 0):.3f} |",
            f"| Ср. ходов до исправления | {er.get('avg_turns_to_recovery', 0):.1f} |",
            f"| Persistent Error Rate | {er.get('persistent_error_rate', 0):.3f} |", "",
        ])
    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="Generate thesis report tables")
    parser.add_argument("--results", type=str, default="evaluation/reports/benchmark_results.json")
    parser.add_argument("--output", type=str, default="evaluation/reports/thesis_tables.md")
    args = parser.parse_args()

    results_path = Path(args.results)
    if not results_path.exists():
        logger.error(f"Results not found: {results_path}")
        return 1

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    report = generate_thesis_report(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Thesis report saved to {output_path}")
    print(f"Tables generated: {report.count('### Таблица')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
