"""
Dataset validation module for REAP calibration datasets.

Validates against the JSON schema in contracts/calibration-dataset-schema.json
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import Counter

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import jsonschema

logger = logging.getLogger(__name__)

# Expected domain distribution (percentages)
DOMAIN_TARGETS = {
    "code": 0.20,
    "math": 0.20,
    "physics": 0.15,
    "chemistry": 0.15,
    "biology": 0.15,
    "socratic": 0.15
}

TOLERANCE = 0.05  # 5% tolerance for distribution


def load_schema(schema_path: str = None) -> dict:
    """Load the calibration dataset JSON schema."""
    if schema_path is None:
        # Default path relative to project root
        schema_path = Path(__file__).parent.parent / "specs" / "003-glm-math-pruning" / "contracts" / "calibration-dataset-schema.json"

    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_schema(data: dict, schema: dict = None) -> Tuple[bool, List[str]]:
    """
    Validate dataset against JSON schema.

    Args:
        data: Dataset dictionary
        schema: JSON schema (loads default if None)

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    if schema is None:
        schema = load_schema()

    errors = []
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation error: {e.message}")
        errors.append(f"  Path: {'.'.join(str(p) for p in e.path)}")

    return len(errors) == 0, errors


def validate_distribution(examples: List[dict], tolerance: float = TOLERANCE) -> Tuple[bool, Dict[str, float], List[str]]:
    """
    Validate domain distribution is balanced within tolerance.

    Args:
        examples: List of calibration examples
        tolerance: Acceptable deviation from target (default 5%)

    Returns:
        Tuple of (is_valid, actual_distribution, list of warnings)
    """
    total = len(examples)
    if total == 0:
        return False, {}, ["No examples in dataset"]

    # Count domains
    domain_counts = Counter(ex.get("domain", "unknown") for ex in examples)

    # Calculate actual percentages
    actual = {domain: count / total for domain, count in domain_counts.items()}

    warnings = []
    is_valid = True

    for domain, target in DOMAIN_TARGETS.items():
        actual_pct = actual.get(domain, 0)
        deviation = abs(actual_pct - target)

        if deviation > tolerance:
            is_valid = False
            warnings.append(
                f"Domain '{domain}' is {deviation*100:.1f}% off target "
                f"(actual: {actual_pct*100:.1f}%, target: {target*100:.1f}%)"
            )

    # Check for unknown domains
    unknown = set(actual.keys()) - set(DOMAIN_TARGETS.keys())
    if unknown:
        warnings.append(f"Unknown domains found: {unknown}")

    return is_valid, actual, warnings


def validate_examples(examples: List[dict]) -> Tuple[bool, List[str]]:
    """
    Validate individual examples for quality.

    Args:
        examples: List of calibration examples

    Returns:
        Tuple of (all_valid, list of issues)
    """
    issues = []
    seen_instructions = set()

    for i, ex in enumerate(examples):
        # Check for duplicates
        instruction = ex.get("instruction", "")
        if instruction in seen_instructions:
            issues.append(f"Example {i}: Duplicate instruction")
        seen_instructions.add(instruction)

        # Check instruction length
        if len(instruction) < 10:
            issues.append(f"Example {i}: Instruction too short ({len(instruction)} chars)")
        if len(instruction) > 2000:
            issues.append(f"Example {i}: Instruction too long ({len(instruction)} chars)")

        # Check output has step-by-step reasoning
        output = ex.get("output", "")
        if len(output) < 50:
            issues.append(f"Example {i}: Output too short ({len(output)} chars)")

        # Simple heuristic for step-by-step
        has_steps = any(marker in output.lower() for marker in [
            "step 1", "step 2", "first", "second", "then", "next",
            "1.", "2.", "1)", "2)", "```"
        ])
        if not has_steps and len(output) > 100:
            issues.append(f"Example {i}: Output may lack step-by-step reasoning")

    return len(issues) == 0, issues


def validate_dataset_file(filepath: str, schema_path: str = None) -> Dict[str, Any]:
    """
    Validate a complete dataset file.

    Args:
        filepath: Path to JSONL dataset file
        schema_path: Optional path to JSON schema

    Returns:
        Validation report dictionary
    """
    report = {
        "filepath": filepath,
        "is_valid": True,
        "total_examples": 0,
        "schema_valid": False,
        "distribution_valid": False,
        "examples_valid": False,
        "errors": [],
        "warnings": [],
        "distribution": {}
    }

    # Load examples from JSONL
    try:
        examples = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    examples.append(json.loads(line))
        report["total_examples"] = len(examples)
    except Exception as e:
        report["errors"].append(f"Failed to load file: {e}")
        report["is_valid"] = False
        return report

    # Validate distribution
    dist_valid, actual_dist, dist_warnings = validate_distribution(examples)
    report["distribution_valid"] = dist_valid
    report["distribution"] = actual_dist
    report["warnings"].extend(dist_warnings)

    # Validate individual examples
    ex_valid, ex_issues = validate_examples(examples)
    report["examples_valid"] = ex_valid
    if ex_issues:
        # Only report first 10 issues
        report["warnings"].extend(ex_issues[:10])
        if len(ex_issues) > 10:
            report["warnings"].append(f"... and {len(ex_issues) - 10} more issues")

    # Overall validity
    report["is_valid"] = dist_valid and ex_valid

    return report


def print_report(report: Dict[str, Any]):
    """Print a formatted validation report."""
    print("\n" + "=" * 60)
    print("DATASET VALIDATION REPORT")
    print("=" * 60)
    print(f"File: {report['filepath']}")
    print(f"Total examples: {report['total_examples']}")
    print(f"Overall valid: {'[OK]' if report['is_valid'] else '[FAIL]'}")
    print()

    print("Distribution:")
    for domain, pct in sorted(report.get('distribution', {}).items()):
        target = DOMAIN_TARGETS.get(domain, 0)
        status = "[OK]" if abs(pct - target) <= TOLERANCE else "[!]"
        print(f"  {domain:12} {pct*100:5.1f}% (target: {target*100:.0f}%) {status}")

    if report['errors']:
        print("\nErrors:")
        for err in report['errors']:
            print(f"  [FAIL] {err}")

    if report['warnings']:
        print("\nWarnings:")
        for warn in report['warnings'][:15]:
            print(f"  [!] {warn}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validate_dataset.py <dataset.jsonl>")
        sys.exit(1)

    report = validate_dataset_file(sys.argv[1])
    print_report(report)
    sys.exit(0 if report["is_valid"] else 1)
