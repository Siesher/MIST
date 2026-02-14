#!/usr/bin/env python3
"""
Generate multi-domain STEM calibration dataset for REAP pruning.

Uses Cerebras API with 10-key rotation for fast generation.
Supports checkpointing for resume on interruption.

Usage:
    cd C:/Work/MITS
    python training/generate_calibration.py --num-examples 1000
    python training/generate_calibration.py --num-examples 100 --domains code,math
"""

# === PATH SETUP (must be before any local imports) ===
import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
# =====================================================

import argparse
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from tqdm import tqdm

from training.cerebras_client import CerebrasClient
from training.prompts.base_template import (
    load_domain_prompts,
    create_generation_prompt,
    get_domain_config,
    DOMAIN_CONFIG
)
from training.validate_dataset import validate_dataset_file, print_report

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_checkpoint(checkpoint_path: str) -> Dict[str, Any]:
    """Load checkpoint if exists."""
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"generated": [], "domain_counts": {}, "last_index": 0}


def save_checkpoint(checkpoint_path: str, data: Dict[str, Any]):
    """Save checkpoint for resume."""
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def calculate_domain_targets(total_examples: int, domains: List[str]) -> Dict[str, int]:
    """Calculate target counts per domain based on total examples."""
    targets = {}

    # Get configured percentages
    total_pct = sum(DOMAIN_CONFIG[d]["target_count"] for d in domains if d in DOMAIN_CONFIG)
    if total_pct == 0:
        total_pct = len(domains) * 100

    for domain in domains:
        if domain in DOMAIN_CONFIG:
            pct = DOMAIN_CONFIG[domain]["target_count"] / 1000  # Original target was for 1000
            targets[domain] = int(total_examples * pct)
        else:
            targets[domain] = total_examples // len(domains)

    # Adjust to match total exactly
    diff = total_examples - sum(targets.values())
    if diff != 0:
        # Add/subtract from largest domain
        largest = max(targets, key=targets.get)
        targets[largest] += diff

    return targets


def generate_example(
    client: CerebrasClient,
    domain: str,
    prompts: List[Dict],
    max_retries: int = 3
) -> Optional[Dict[str, Any]]:
    """Generate a single calibration example."""
    template = random.choice(prompts)
    prompt_data = create_generation_prompt(template, domain)

    for attempt in range(max_retries):
        try:
            response = client.generate(
                prompt=prompt_data["user"],
                system_prompt=prompt_data["system"],
                max_tokens=2048,
                temperature=0.7
            )

            if response and len(response) > 50:
                return {
                    "instruction": prompt_data["user"],
                    "input": "",
                    "output": response,
                    "domain": domain,
                    "subtopic": prompt_data["subtopic"],
                    "difficulty": prompt_data["difficulty"]
                }
        except Exception as e:
            logger.warning(f"Generation failed (attempt {attempt + 1}): {e}")
            time.sleep(1)

    return None


def generate_dataset(
    output_path: str,
    num_examples: int = 1000,
    domains: List[str] = None,
    env_file: str = ".env",
    checkpoint_interval: int = 10
) -> str:
    """
    Generate the full calibration dataset.

    Args:
        output_path: Path to output JSONL file
        num_examples: Total number of examples to generate
        domains: List of domains to include
        env_file: Path to .env file with API keys
        checkpoint_interval: Save checkpoint every N examples

    Returns:
        Path to generated dataset
    """
    if domains is None:
        domains = list(DOMAIN_CONFIG.keys())

    # Validate domains
    for d in domains:
        if d not in DOMAIN_CONFIG:
            raise ValueError(f"Unknown domain: {d}")

    # Calculate targets
    targets = calculate_domain_targets(num_examples, domains)
    logger.info(f"Target distribution: {targets}")

    # Load prompts for each domain
    prompts_dir = Path(__file__).parent / "prompts"
    domain_prompts = {}
    for domain in domains:
        try:
            domain_prompts[domain] = load_domain_prompts(domain, prompts_dir)
            logger.info(f"Loaded {len(domain_prompts[domain])} prompts for {domain}")
        except FileNotFoundError:
            logger.error(f"Prompt file not found for domain: {domain}")
            raise

    # Setup checkpoint
    checkpoint_path = output_path + ".checkpoint"
    checkpoint = load_checkpoint(checkpoint_path)

    # Initialize client
    client = CerebrasClient(env_file=env_file)
    logger.info(f"Initialized Cerebras client with {len(client.api_keys)} API keys")

    # Resume from checkpoint
    examples = checkpoint.get("generated", [])
    domain_counts = checkpoint.get("domain_counts", {d: 0 for d in domains})

    # Calculate remaining
    remaining = {}
    for domain in domains:
        remaining[domain] = max(0, targets[domain] - domain_counts.get(domain, 0))

    total_remaining = sum(remaining.values())
    logger.info(f"Resuming from {len(examples)} examples, {total_remaining} remaining")

    if total_remaining == 0:
        logger.info("Dataset already complete!")
    else:
        # Create generation queue
        queue = []
        for domain, count in remaining.items():
            queue.extend([domain] * count)
        random.shuffle(queue)

        # Progress bar
        pbar = tqdm(total=total_remaining, desc="Generating", unit="ex")

        start_time = time.time()
        generated_count = 0

        for domain in queue:
            example = generate_example(client, domain, domain_prompts[domain])

            if example:
                examples.append(example)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                generated_count += 1
                pbar.update(1)

                # ETA calculation
                elapsed = time.time() - start_time
                rate = generated_count / elapsed if elapsed > 0 else 0
                remaining_count = total_remaining - generated_count
                eta = remaining_count / rate if rate > 0 else 0
                pbar.set_postfix({
                    "rate": f"{rate:.1f}/s",
                    "eta": f"{eta/60:.1f}m",
                    domain: domain_counts[domain]
                })

                # Checkpoint
                if generated_count % checkpoint_interval == 0:
                    save_checkpoint(checkpoint_path, {
                        "generated": examples,
                        "domain_counts": domain_counts,
                        "last_index": generated_count
                    })

        pbar.close()

    # Save final dataset
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for example in examples:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

    # Clean up checkpoint
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    # Log stats
    stats = client.get_stats()
    logger.info(f"Generation complete: {len(examples)} examples")
    logger.info(f"Total API requests: {stats['total_requests']}")
    logger.info(f"Total tokens used: {stats['total_tokens']}")
    logger.info(f"Domain distribution: {domain_counts}")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate STEM calibration dataset for REAP pruning"
    )
    parser.add_argument(
        "--output", "-o",
        default="training/calibration_data/stem_calibration.jsonl",
        help="Output file path"
    )
    parser.add_argument(
        "--num-examples", "-n",
        type=int,
        default=1000,
        help="Number of examples to generate"
    )
    parser.add_argument(
        "--domains", "-d",
        default="code,math,physics,chemistry,biology,socratic",
        help="Comma-separated list of domains"
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file with API keys"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate dataset after generation"
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Save checkpoint every N examples"
    )

    args = parser.parse_args()

    domains = [d.strip() for d in args.domains.split(",")]

    logger.info(f"Starting generation: {args.num_examples} examples")
    logger.info(f"Domains: {domains}")
    logger.info(f"Output: {args.output}")

    try:
        output_path = generate_dataset(
            output_path=args.output,
            num_examples=args.num_examples,
            domains=domains,
            env_file=args.env_file,
            checkpoint_interval=args.checkpoint_interval
        )

        if args.validate:
            logger.info("Validating generated dataset...")
            report = validate_dataset_file(output_path)
            print_report(report)

            if not report["is_valid"]:
                logger.warning("Dataset validation failed!")
                return 1

        logger.info(f"Dataset saved to: {output_path}")
        return 0

    except KeyboardInterrupt:
        logger.info("Generation interrupted. Checkpoint saved for resume.")
        return 1
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise


if __name__ == "__main__":
    exit(main())
