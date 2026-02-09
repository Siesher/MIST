"""
Affect Detection Accuracy Benchmark

Computes per-class F1, precision, recall for rule-based vs ML detector.

Usage:
    python -m evaluation.benchmarks.affect_accuracy \
        --test-data data/training/affect_labels.jsonl \
        --ml-model data/models/rubert_affect \
        --output evaluation/reports/affect_accuracy.json
"""

import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

LABELS = ["neutral", "frustrated", "confused", "engaged", "confident"]


@dataclass
class ClassMetrics:
    """Per-class metrics."""
    label: str = ""
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    support: int = 0


@dataclass
class DetectorMetrics:
    """Metrics for one detector."""
    detector_name: str = ""
    macro_f1: float = 0.0
    accuracy: float = 0.0
    per_class: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AffectAccuracyResult:
    """Full benchmark result."""
    rules_metrics: Dict[str, Any] = field(default_factory=dict)
    ml_metrics: Dict[str, Any] = field(default_factory=dict)
    ml_improvement_f1: float = 0.0
    test_samples: int = 0


def compute_class_metrics(y_true: List[str], y_pred: List[str]) -> List[ClassMetrics]:
    """Compute per-class precision, recall, F1."""
    results = []
    for label in LABELS:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        support = sum(1 for t in y_true if t == label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        results.append(ClassMetrics(label=label, precision=precision, recall=recall, f1=f1, support=support))
    return results


def compute_macro_f1(class_metrics: List[ClassMetrics]) -> float:
    """Compute macro-averaged F1."""
    f1s = [m.f1 for m in class_metrics if m.support > 0]
    return sum(f1s) / len(f1s) if f1s else 0.0


def evaluate_rules(texts: List[str], true_labels: List[str]) -> DetectorMetrics:
    """Evaluate rule-based detector."""
    from training.scripts.generate_affect_labels import classify_text

    pred_labels = [classify_text(text) for text in texts]
    class_metrics = compute_class_metrics(true_labels, pred_labels)
    accuracy = sum(1 for t, p in zip(true_labels, pred_labels) if t == p) / len(true_labels)

    return DetectorMetrics(
        detector_name="rules",
        macro_f1=compute_macro_f1(class_metrics),
        accuracy=accuracy,
        per_class=[asdict(m) for m in class_metrics],
    )


def evaluate_ml(texts: List[str], true_labels: List[str], model_path: str) -> DetectorMetrics:
    """Evaluate ML-based detector."""
    try:
        from src.models.affective_ml_detector import AffectiveMLDetector
    except ImportError:
        logger.error("AffectiveMLDetector not available")
        return DetectorMetrics(detector_name="ml")

    detector = AffectiveMLDetector(model_path=model_path)
    if not detector.is_available:
        logger.warning(f"ML model not available at {model_path}")
        return DetectorMetrics(detector_name="ml")

    pred_labels = [detector.predict(text)[0] for text in texts]
    class_metrics = compute_class_metrics(true_labels, pred_labels)
    accuracy = sum(1 for t, p in zip(true_labels, pred_labels) if t == p) / len(true_labels)

    return DetectorMetrics(
        detector_name="ml",
        macro_f1=compute_macro_f1(class_metrics),
        accuracy=accuracy,
        per_class=[asdict(m) for m in class_metrics],
    )


def main():
    parser = argparse.ArgumentParser(description="Affect detection benchmark")
    parser.add_argument("--test-data", type=str, required=True)
    parser.add_argument("--ml-model", type=str, default="data/models/rubert_affect")
    parser.add_argument("--output", type=str, default="evaluation/reports/affect_accuracy.json")
    args = parser.parse_args()

    texts, labels = [], []
    with open(args.test_data, "r", encoding="utf-8") as f:
        for line in f:
            sample = json.loads(line)
            if sample.get("label") in LABELS:
                texts.append(sample["text"])
                labels.append(sample["label"])

    logger.info(f"Loaded {len(texts)} test samples")

    rules = evaluate_rules(texts, labels)
    ml = evaluate_ml(texts, labels, args.ml_model)

    result = AffectAccuracyResult(
        rules_metrics=asdict(rules),
        ml_metrics=asdict(ml),
        ml_improvement_f1=ml.macro_f1 - rules.macro_f1,
        test_samples=len(texts),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)

    print(f"\n{'Detector':<10} {'Macro F1':>10} {'Accuracy':>10}")
    print("-" * 32)
    print(f"{'Rules':<10} {rules.macro_f1:>10.4f} {rules.accuracy:>10.4f}")
    print(f"{'ML':<10} {ml.macro_f1:>10.4f} {ml.accuracy:>10.4f}")
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
