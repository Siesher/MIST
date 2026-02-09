"""
Knowledge Prediction Benchmark

Computes AUC, RMSE, accuracy for BKT and DKT on test interaction data.

Usage:
    python -m evaluation.benchmarks.knowledge_prediction \
        --test-data data/training/assistments_test.pt \
        --dkt-weights data/models/dkt_pretrained.pt \
        --output evaluation/reports/knowledge_prediction.json
"""

import json
import logging
import argparse
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ModelMetrics:
    """Metrics for a single model."""
    model_name: str = ""
    auc: float = 0.0
    rmse: float = 0.0
    accuracy: float = 0.0
    num_predictions: int = 0


@dataclass
class KnowledgePredictionResult:
    """Full benchmark result."""
    bkt_metrics: Dict[str, Any] = field(default_factory=dict)
    dkt_metrics: Dict[str, Any] = field(default_factory=dict)
    dkt_improvement_auc: float = 0.0
    dkt_improvement_rmse: float = 0.0


def compute_auc(y_true: List[int], y_scores: List[float]) -> float:
    """Compute AUC using trapezoidal rule."""
    if not y_true or not y_scores:
        return 0.0

    pairs = sorted(zip(y_scores, y_true), reverse=True)
    tp, fp = 0, 0
    total_pos = sum(y_true)
    total_neg = len(y_true) - total_pos

    if total_pos == 0 or total_neg == 0:
        return 0.5

    auc = 0.0
    prev_fpr, prev_tpr = 0.0, 0.0
    for score, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tpr = tp / total_pos
        fpr = fp / total_neg
        auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2
        prev_fpr, prev_tpr = fpr, tpr

    return auc


def compute_rmse(y_true: List[int], y_scores: List[float]) -> float:
    """Compute RMSE."""
    if not y_true:
        return 0.0
    mse = sum((t - s) ** 2 for t, s in zip(y_true, y_scores)) / len(y_true)
    return math.sqrt(mse)


def compute_accuracy(y_true: List[int], y_scores: List[float], threshold: float = 0.5) -> float:
    """Compute accuracy with threshold."""
    if not y_true:
        return 0.0
    correct = sum(1 for t, s in zip(y_true, y_scores) if (s >= threshold) == (t == 1))
    return correct / len(y_true)


def evaluate_bkt(test_sequences: List[List[Tuple[int, bool]]]) -> ModelMetrics:
    """Evaluate BKT on test sequences."""
    from src.models.knowledge_tracing import KnowledgeTracker

    y_true, y_scores = [], []
    tracker = KnowledgeTracker()

    for seq in test_sequences:
        tracker.reset()
        for skill_id, correct in seq:
            mastery = tracker.get_mastery(skill_id)
            y_scores.append(mastery)
            y_true.append(1 if correct else 0)
            tracker.update(skill_id, correct)

    return ModelMetrics(
        model_name="BKT",
        auc=compute_auc(y_true, y_scores),
        rmse=compute_rmse(y_true, y_scores),
        accuracy=compute_accuracy(y_true, y_scores),
        num_predictions=len(y_true),
    )


def evaluate_dkt(test_sequences: List[List[Tuple[int, bool]]], weights_path: str) -> ModelMetrics:
    """Evaluate DKT on test sequences."""
    try:
        from src.models.dkt_model import DKTModel
    except ImportError:
        logger.error("DKT model not available")
        return ModelMetrics(model_name="DKT")

    model = DKTModel.from_pretrained(weights_path)
    if model is None:
        logger.error(f"Could not load DKT weights from {weights_path}")
        return ModelMetrics(model_name="DKT")

    y_true, y_scores = [], []

    for seq in test_sequences:
        history = []
        for skill_id, correct in seq:
            if history:
                predictions = model.predict_next(history)
                pred = predictions.get(skill_id, 0.5)
                y_scores.append(pred)
                y_true.append(1 if correct else 0)
            history.append((skill_id, correct))

    return ModelMetrics(
        model_name="DKT",
        auc=compute_auc(y_true, y_scores),
        rmse=compute_rmse(y_true, y_scores),
        accuracy=compute_accuracy(y_true, y_scores),
        num_predictions=len(y_true),
    )


def load_test_sequences(test_data_path: Path) -> List[List[Tuple[int, bool]]]:
    """Load test sequences from .pt or .jsonl file."""
    if test_data_path.suffix == ".pt":
        import torch
        data = torch.load(str(test_data_path), map_location="cpu")
        if isinstance(data, dict):
            sequences = data.get("test_sequences", data.get("sequences", []))
        else:
            sequences = data

        result = []
        for seq in sequences:
            if hasattr(seq, "tolist"):
                seq = seq.tolist()
            pairs = []
            for item in seq:
                if isinstance(item, (list, tuple)):
                    pairs.append((int(item[0]), bool(item[1])))
                else:
                    item = int(item)
                    if item == 0:
                        continue
                    skill_id = item // 2
                    correct = bool(item % 2)
                    pairs.append((skill_id, correct))
            if pairs:
                result.append(pairs)
        return result

    elif test_data_path.suffix == ".jsonl":
        result = []
        with open(test_data_path, "r") as f:
            for line in f:
                data = json.loads(line)
                seq = [(int(s), bool(c)) for s, c in data.get("interactions", [])]
                if seq:
                    result.append(seq)
        return result

    else:
        logger.error(f"Unsupported format: {test_data_path.suffix}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Knowledge prediction benchmark")
    parser.add_argument("--test-data", type=str, required=True)
    parser.add_argument("--dkt-weights", type=str, default="data/models/dkt_pretrained.pt")
    parser.add_argument("--output", type=str, default="evaluation/reports/knowledge_prediction.json")
    args = parser.parse_args()

    sequences = load_test_sequences(Path(args.test_data))
    if not sequences:
        logger.error("No test sequences loaded")
        return 1

    logger.info(f"Loaded {len(sequences)} test sequences")

    bkt = evaluate_bkt(sequences)
    dkt = evaluate_dkt(sequences, args.dkt_weights)

    result = KnowledgePredictionResult(
        bkt_metrics=asdict(bkt),
        dkt_metrics=asdict(dkt),
        dkt_improvement_auc=dkt.auc - bkt.auc,
        dkt_improvement_rmse=bkt.rmse - dkt.rmse,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2)

    print(f"\n{'Model':<8} {'AUC':>8} {'RMSE':>8} {'Accuracy':>10}")
    print("-" * 38)
    print(f"{'BKT':<8} {bkt.auc:>8.4f} {bkt.rmse:>8.4f} {bkt.accuracy:>10.4f}")
    print(f"{'DKT':<8} {dkt.auc:>8.4f} {dkt.rmse:>8.4f} {dkt.accuracy:>10.4f}")
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
