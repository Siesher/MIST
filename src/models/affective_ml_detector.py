"""
ML-based Affective State Detector using fine-tuned RuBERT.

Replaces rule-based detection with a transformer classifier trained on
labeled tutoring dialog data. Falls back to rule-based if model unavailable.

Model: DeepPavlov/rubert-base-cased fine-tuned on 5-class emotion classification.
Classes: neutral, frustrated, confused, engaged, confident

Memory: ~400MB for rubert-base-cased (fits easily alongside GLM on 8GB VRAM).
"""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Default label mapping (matches training notebook)
DEFAULT_LABEL_MAP = {
    "neutral": 0,
    "frustrated": 1,
    "confused": 2,
    "engaged": 3,
    "confident": 4,
}


class AffectiveMLDetector:
    """
    ML-based affective state detector using fine-tuned RuBERT.

    Loads a HuggingFace sequence classification model and predicts
    emotion from student message text.
    """

    def __init__(
        self,
        model_path: str = "data/models/rubert_affect",
        device: str = "cpu",
        max_length: int = 128,
    ):
        """
        Initialize ML detector.

        Args:
            model_path: Path to fine-tuned RuBERT model directory
            device: Device for inference ('cpu' or 'cuda')
            max_length: Maximum sequence length for tokenization
        """
        self.model_path = Path(model_path)
        self.device = device
        self.max_length = max_length
        self.model = None
        self.tokenizer = None
        self.label_map: Dict[str, int] = {}
        self.id_to_label: Dict[int, str] = {}
        self._loaded = False

        self._try_load()

    def _try_load(self):
        """Attempt to load the model. Log warning if unavailable."""
        if not self.model_path.exists():
            logger.warning(
                f"RuBERT affect model not found at {self.model_path}. "
                f"ML detection unavailable — use rule-based fallback."
            )
            return

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
            self.model = AutoModelForSequenceClassification.from_pretrained(
                str(self.model_path)
            )
            self.model.to(self.device)
            self.model.eval()

            # Load label mapping from model config or metadata
            metadata_path = self.model_path / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, "r") as f:
                    meta = json.load(f)
                self.label_map = meta.get("label_map", DEFAULT_LABEL_MAP)
            elif hasattr(self.model.config, "label2id"):
                self.label_map = self.model.config.label2id
            else:
                self.label_map = DEFAULT_LABEL_MAP

            self.id_to_label = {v: k for k, v in self.label_map.items()}
            self._loaded = True

            total_params = sum(p.numel() for p in self.model.parameters())
            logger.info(
                f"RuBERT affect model loaded: {total_params:,} params, "
                f"{len(self.label_map)} classes, device={self.device}"
            )
        except ImportError:
            logger.warning(
                "transformers library not installed. ML affect detection unavailable."
            )
        except Exception as e:
            logger.warning(f"Failed to load RuBERT affect model: {e}")

    @property
    def is_available(self) -> bool:
        """Check if ML model is loaded and ready."""
        return self._loaded and self.model is not None

    def predict(self, text: str) -> Tuple[str, float]:
        """
        Predict emotion label from text.

        Args:
            text: Student message text

        Returns:
            (label, confidence) tuple. Label is one of:
            neutral, frustrated, confused, engaged, confident
        """
        if not self.is_available:
            return "neutral", 0.0

        import torch

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)[0]

        pred_id = probs.argmax().item()
        confidence = probs[pred_id].item()
        label = self.id_to_label.get(pred_id, "neutral")

        return label, confidence

    def predict_scores(self, text: str) -> Dict[str, float]:
        """
        Get confidence scores for all emotion classes.

        Args:
            text: Student message text

        Returns:
            Dictionary mapping label -> confidence score
        """
        if not self.is_available:
            return {label: 0.2 for label in DEFAULT_LABEL_MAP}

        import torch

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)[0]

        return {
            self.id_to_label.get(i, f"class_{i}"): probs[i].item()
            for i in range(len(probs))
        }
