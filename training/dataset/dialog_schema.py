"""
Dialog annotation schema and validation.

Validates move_type, emotion, error_type, is_correct fields per turn.
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional


class MoveType(str, Enum):
    SCAFFOLDING = "scaffolding"
    PROBLEMATIZE = "problematize"
    RECTIFY = "rectify"
    ENCOURAGE = "encourage"
    HINT = "hint"
    TELL = "tell"
    CLARIFY = "clarify"
    SYSTEM = "system"


class Emotion(str, Enum):
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    CONFUSED = "confused"
    CONFIDENT = "confident"
    CURIOUS = "curious"
    ENGAGED = "engaged"
    BORED = "bored"


class ErrorType(str, Enum):
    NONE = "none"
    CONCEPTUAL = "conceptual"       # Wrong understanding of concept
    PROCEDURAL = "procedural"       # Wrong execution of procedure
    ARITHMETIC = "arithmetic"       # Calculation error
    NOTATION = "notation"           # Wrong notation / formatting
    INCOMPLETE = "incomplete"       # Partial answer


VALID_ROLES = {"student", "tutor", "system"}
VALID_TOPICS = {"derivatives", "integrals", "limits", "equations", "linear_algebra", "series"}
VALID_DIFFICULTIES = {"easy", "medium", "hard", "olympiad"}
VALID_PERSONAS = {"novice", "intermediate", "advanced", "confused", "curious"}


@dataclass
class ValidationError:
    dialog_id: str
    turn_index: int
    field: str
    message: str

    def __str__(self):
        return f"[{self.dialog_id}] turn {self.turn_index}, {self.field}: {self.message}"


def validate_turn(dialog_id: str, turn_index: int, turn: dict) -> List[ValidationError]:
    """Validate a single dialog turn."""
    errors = []

    # Role is required
    role = turn.get("role")
    if role not in VALID_ROLES:
        errors.append(ValidationError(dialog_id, turn_index, "role",
                                      f"Invalid role '{role}', must be one of {VALID_ROLES}"))

    # Content is required
    content = turn.get("content", "")
    if not content or not content.strip():
        errors.append(ValidationError(dialog_id, turn_index, "content", "Empty content"))

    # Tutor-specific fields
    if role == "tutor":
        move = turn.get("move")
        if move:
            try:
                MoveType(move)
            except ValueError:
                errors.append(ValidationError(dialog_id, turn_index, "move",
                                              f"Invalid move '{move}', must be one of {[m.value for m in MoveType]}"))

    # Optional annotation fields
    emotion = turn.get("emotion")
    if emotion:
        try:
            Emotion(emotion)
        except ValueError:
            errors.append(ValidationError(dialog_id, turn_index, "emotion",
                                          f"Invalid emotion '{emotion}'"))

    error_type = turn.get("error_type")
    if error_type:
        try:
            ErrorType(error_type)
        except ValueError:
            errors.append(ValidationError(dialog_id, turn_index, "error_type",
                                          f"Invalid error_type '{error_type}'"))

    is_correct = turn.get("is_correct")
    if is_correct is not None and not isinstance(is_correct, bool):
        errors.append(ValidationError(dialog_id, turn_index, "is_correct",
                                      f"is_correct must be bool, got {type(is_correct).__name__}"))

    return errors


def validate_dialog(dialog: dict) -> List[ValidationError]:
    """Validate a complete dialog object."""
    errors = []
    dialog_id = dialog.get("id", "unknown")

    # Required top-level fields
    if not dialog.get("id"):
        errors.append(ValidationError(dialog_id, -1, "id", "Missing dialog id"))

    # Task validation
    task = dialog.get("task", {})
    if not task:
        errors.append(ValidationError(dialog_id, -1, "task", "Missing task"))
    else:
        if not task.get("problem"):
            errors.append(ValidationError(dialog_id, -1, "task.problem", "Missing problem"))
        topic = task.get("topic")
        if topic and topic not in VALID_TOPICS:
            errors.append(ValidationError(dialog_id, -1, "task.topic",
                                          f"Invalid topic '{topic}'"))
        difficulty = task.get("difficulty")
        if difficulty and difficulty not in VALID_DIFFICULTIES:
            errors.append(ValidationError(dialog_id, -1, "task.difficulty",
                                          f"Invalid difficulty '{difficulty}'"))

    # Persona validation
    persona = dialog.get("student_persona")
    if persona and persona not in VALID_PERSONAS:
        errors.append(ValidationError(dialog_id, -1, "student_persona",
                                      f"Invalid persona '{persona}'"))

    # Turns validation
    turns = dialog.get("turns", [])
    if not turns:
        errors.append(ValidationError(dialog_id, -1, "turns", "No turns"))
    else:
        for i, turn in enumerate(turns):
            errors.extend(validate_turn(dialog_id, i, turn))

        # Check first turn is from student
        if turns[0].get("role") != "student":
            errors.append(ValidationError(dialog_id, 0, "role",
                                          "First turn should be from student"))

        # Check alternation (soft check — allow consecutive same-role)
        student_count = sum(1 for t in turns if t.get("role") == "student")
        tutor_count = sum(1 for t in turns if t.get("role") == "tutor")
        if student_count == 0:
            errors.append(ValidationError(dialog_id, -1, "turns", "No student turns"))
        if tutor_count == 0:
            errors.append(ValidationError(dialog_id, -1, "turns", "No tutor turns"))

        # Speaker ratio check
        total = student_count + tutor_count
        if total > 0:
            ratio = min(student_count, tutor_count) / total
            if ratio < 0.25:
                errors.append(ValidationError(dialog_id, -1, "turns",
                                              f"Unbalanced speaker ratio: {student_count}S/{tutor_count}T"))

    return errors


def validate_dataset(path: Path, strict: bool = False) -> dict:
    """
    Validate an entire JSONL dataset.

    Args:
        path: Path to JSONL file
        strict: If True, treat warnings as errors

    Returns:
        Dict with validation results
    """
    if not path.exists():
        return {"error": f"File not found: {path}"}

    total = 0
    valid = 0
    invalid = 0
    all_errors = []

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                dialog = json.loads(line)
            except json.JSONDecodeError as e:
                all_errors.append(f"Line {line_num}: JSON parse error: {e}")
                invalid += 1
                total += 1
                continue

            total += 1
            errors = validate_dialog(dialog)

            if errors:
                invalid += 1
                for err in errors:
                    all_errors.append(str(err))
            else:
                valid += 1

    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "pass_rate": valid / total if total > 0 else 0,
        "errors": all_errors[:100],  # Cap at 100 errors
        "total_errors": len(all_errors)
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python dialog_schema.py <path_to_jsonl>")
        sys.exit(1)

    path = Path(sys.argv[1])
    result = validate_dataset(path)

    print(f"\nValidation Results for {path}")
    print(f"{'='*50}")
    print(f"Total dialogs:  {result['total']}")
    print(f"Valid:          {result['valid']}")
    print(f"Invalid:        {result['invalid']}")
    print(f"Pass rate:      {result['pass_rate']:.1%}")

    if result.get("errors"):
        print(f"\nFirst {min(20, len(result['errors']))} errors:")
        for err in result["errors"][:20]:
            print(f"  {err}")
