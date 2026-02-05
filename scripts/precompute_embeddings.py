#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-compute embeddings for MITS RAG system.

This script pre-computes and caches embeddings for hints and misconceptions
to speed up RAG retrieval at runtime.

Usage:
    python scripts/precompute_embeddings.py [--model MODEL] [--output DIR]
"""

import argparse
import json
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_hints(knowledge_path: Path) -> List[Dict[str, Any]]:
    """Load all hints from knowledge base."""
    hints = []
    hints_path = knowledge_path / "hints"

    if not hints_path.exists():
        logger.warning(f"Hints path not found: {hints_path}")
        return hints

    # Load JSON files
    for file in hints_path.glob("*.json"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            topic = file.stem
            for hint in data.get("hints", []):
                hint["_topic"] = topic
                hint["_source"] = str(file)
                hints.append(hint)
            logger.info(f"Loaded {len(data.get('hints', []))} hints from {file.name}")
        except Exception as e:
            logger.error(f"Error loading {file}: {e}")

    # Load JSONL files
    for file in hints_path.glob("*.jsonl"):
        try:
            topic = file.stem
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        hint = json.loads(line)
                        hint["_topic"] = topic
                        hint["_source"] = str(file)
                        hints.append(hint)
        except Exception as e:
            logger.error(f"Error loading {file}: {e}")

    return hints


def load_misconceptions(knowledge_path: Path) -> List[Dict[str, Any]]:
    """Load all misconceptions from knowledge base."""
    misconceptions = []
    misc_path = knowledge_path / "misconceptions"

    if not misc_path.exists():
        logger.warning(f"Misconceptions path not found: {misc_path}")
        return misconceptions

    def load_from_path(path: Path):
        # JSON files
        for file in path.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for misc in data.get("misconceptions", []):
                    misc["_source"] = str(file)
                    misconceptions.append(misc)
                logger.info(f"Loaded {len(data.get('misconceptions', []))} misconceptions from {file.name}")
            except Exception as e:
                logger.error(f"Error loading {file}: {e}")

        # JSONL files
        for file in path.glob("*.jsonl"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            misc = json.loads(line)
                            misc["_source"] = str(file)
                            misconceptions.append(misc)
            except Exception as e:
                logger.error(f"Error loading {file}: {e}")

    # Load from main directory
    load_from_path(misc_path)

    # Load from subdirectories
    for subdir in misc_path.iterdir():
        if subdir.is_dir():
            load_from_path(subdir)

    return misconceptions


def create_hint_text(hint: Dict[str, Any]) -> str:
    """Create text representation of hint for embedding."""
    parts = []

    # Include Russian hint (primary)
    if hint.get("hint_ru"):
        parts.append(hint["hint_ru"])
    elif hint.get("content"):
        parts.append(hint["content"])

    # Include skill and trigger for better matching
    if hint.get("skill"):
        parts.append(f"навык: {hint['skill']}")
    if hint.get("trigger"):
        parts.append(f"триггер: {hint['trigger']}")
    if hint.get("follow_up_question"):
        parts.append(hint["follow_up_question"])

    return " ".join(parts)


def create_misconception_text(misc: Dict[str, Any]) -> str:
    """Create text representation of misconception for embedding."""
    parts = []

    if misc.get("error_pattern"):
        parts.append(misc["error_pattern"])
    if misc.get("correct_form"):
        parts.append(misc["correct_form"])
    if misc.get("explanation_ru"):
        parts.append(misc["explanation_ru"])
    if misc.get("example_ru"):
        parts.append(misc["example_ru"])

    return " ".join(parts)


def compute_embeddings(
    texts: List[str],
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
):
    """Compute embeddings for a list of texts."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError:
        logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
        return None

    logger.info(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)

    logger.info(f"Computing embeddings for {len(texts)} texts...")
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    return embeddings


def save_embeddings(
    output_path: Path,
    hint_embeddings,
    misconception_embeddings,
    hint_ids: List[str],
    misconception_ids: List[str],
    model_name: str
):
    """Save embeddings to disk."""
    output_path.mkdir(parents=True, exist_ok=True)

    # Save as pickle for fast loading
    cache_file = output_path / "embeddings_cache.pkl"
    cache_data = {
        "model_name": model_name,
        "hint_embeddings": hint_embeddings,
        "misconception_embeddings": misconception_embeddings,
        "hint_ids": hint_ids,
        "misconception_ids": misconception_ids
    }

    with open(cache_file, 'wb') as f:
        pickle.dump(cache_data, f)

    logger.info(f"Saved embeddings cache to {cache_file}")

    # Also save metadata as JSON
    metadata_file = output_path / "embeddings_metadata.json"
    metadata = {
        "model_name": model_name,
        "num_hints": len(hint_ids),
        "num_misconceptions": len(misconception_ids),
        "hint_ids": hint_ids,
        "misconception_ids": misconception_ids
    }

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved metadata to {metadata_file}")


def main():
    parser = argparse.ArgumentParser(description="Pre-compute embeddings for MITS RAG")
    parser.add_argument(
        "--model",
        default="paraphrase-multilingual-MiniLM-L12-v2",
        help="Sentence transformer model name"
    )
    parser.add_argument(
        "--knowledge-path",
        default="./data/knowledge",
        help="Path to knowledge base"
    )
    parser.add_argument(
        "--output",
        default="./data/embeddings",
        help="Output directory for embeddings"
    )
    args = parser.parse_args()

    knowledge_path = Path(args.knowledge_path)
    output_path = Path(args.output)

    # Load data
    logger.info("Loading knowledge base...")
    hints = load_hints(knowledge_path)
    misconceptions = load_misconceptions(knowledge_path)

    logger.info(f"Loaded {len(hints)} hints and {len(misconceptions)} misconceptions")

    if not hints and not misconceptions:
        logger.error("No data found to embed!")
        return 1

    # Create text representations
    hint_texts = [create_hint_text(h) for h in hints]
    hint_ids = [h.get("id", f"hint_{i}") for i, h in enumerate(hints)]

    misc_texts = [create_misconception_text(m) for m in misconceptions]
    misc_ids = [m.get("id", f"misc_{i}") for i, m in enumerate(misconceptions)]

    # Compute embeddings
    logger.info("Computing hint embeddings...")
    hint_embeddings = compute_embeddings(hint_texts, args.model) if hint_texts else None

    logger.info("Computing misconception embeddings...")
    misc_embeddings = compute_embeddings(misc_texts, args.model) if misc_texts else None

    if hint_embeddings is None and misc_embeddings is None:
        logger.error("Failed to compute embeddings")
        return 1

    # Save embeddings
    save_embeddings(
        output_path,
        hint_embeddings,
        misc_embeddings,
        hint_ids,
        misc_ids,
        args.model
    )

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
