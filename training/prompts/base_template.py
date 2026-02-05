"""
Base template structure for domain-specific prompt generation.

Each domain prompt file should contain a list of prompt templates
that will be used to generate calibration examples via Cerebras API.
"""

import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class PromptTemplate:
    """A template for generating calibration examples."""
    instruction_template: str
    subtopic: str
    difficulty: str  # basic, intermediate, advanced
    variables: Dict[str, List[str]] = None

    def render(self) -> str:
        """Render the template with random variable substitution."""
        instruction = self.instruction_template
        if self.variables:
            for var_name, var_options in self.variables.items():
                placeholder = "{" + var_name + "}"
                if placeholder in instruction:
                    instruction = instruction.replace(placeholder, random.choice(var_options))
        return instruction


def load_domain_prompts(domain: str, prompts_dir: str = None) -> List[Dict[str, Any]]:
    """
    Load prompt templates for a specific domain.

    Args:
        domain: Domain name (code, math, physics, chemistry, biology, socratic)
        prompts_dir: Directory containing prompt JSON files

    Returns:
        List of prompt template dictionaries
    """
    if prompts_dir is None:
        prompts_dir = Path(__file__).parent

    filepath = Path(prompts_dir) / f"{domain}_prompts.json"

    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get("prompts", [])


def get_system_prompt(domain: str) -> str:
    """Get the system prompt for a specific domain."""
    base_prompt = """You are an expert tutor in {domain}. Generate a detailed, step-by-step response to the following problem or question.

Requirements:
- Break down your solution into clear, numbered steps
- Explain your reasoning at each step
- Use appropriate notation and terminology for the domain
- For code: include working, well-commented code
- For math/science: show all work and intermediate calculations
- End with a clear final answer or conclusion

Be thorough but concise. Aim for educational clarity."""

    domain_specifics = {
        "code": "programming and software development",
        "math": "mathematics including algebra, calculus, statistics, and probability",
        "physics": "physics including mechanics, thermodynamics, and electromagnetism",
        "chemistry": "chemistry including organic, inorganic, and biochemistry",
        "biology": "biology including molecular biology, genetics, and ecology",
        "socratic": "education using the Socratic method - provide hints and guiding questions, not direct answers"
    }

    return base_prompt.format(domain=domain_specifics.get(domain, domain))


def create_generation_prompt(template: Dict[str, Any], domain: str) -> Dict[str, str]:
    """
    Create a full prompt for Cerebras API from a template.

    Args:
        template: Prompt template dictionary
        domain: Domain name

    Returns:
        Dictionary with 'system' and 'user' prompts
    """
    # Render instruction with variable substitution
    instruction = template.get("instruction_template", template.get("instruction", ""))
    variables = template.get("variables", {})

    for var_name, var_options in variables.items():
        placeholder = "{" + var_name + "}"
        if placeholder in instruction:
            instruction = instruction.replace(placeholder, random.choice(var_options))

    return {
        "system": get_system_prompt(domain),
        "user": instruction,
        "subtopic": template.get("subtopic", "general"),
        "difficulty": template.get("difficulty", "intermediate")
    }


def validate_prompt_file(filepath: str) -> tuple[bool, List[str]]:
    """
    Validate a domain prompt file structure.

    Args:
        filepath: Path to the prompt JSON file

    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    if "domain" not in data:
        issues.append("Missing 'domain' field")

    if "prompts" not in data:
        issues.append("Missing 'prompts' field")
        return False, issues

    prompts = data.get("prompts", [])
    if not prompts:
        issues.append("No prompts defined")

    for i, prompt in enumerate(prompts):
        if "instruction_template" not in prompt and "instruction" not in prompt:
            issues.append(f"Prompt {i}: Missing instruction_template or instruction")
        if "subtopic" not in prompt:
            issues.append(f"Prompt {i}: Missing subtopic")
        if "difficulty" not in prompt:
            issues.append(f"Prompt {i}: Missing difficulty")
        elif prompt["difficulty"] not in ["basic", "intermediate", "advanced"]:
            issues.append(f"Prompt {i}: Invalid difficulty '{prompt['difficulty']}'")

    return len(issues) == 0, issues


# Domain configuration
DOMAIN_CONFIG = {
    "code": {
        "target_count": 200,
        "subtopics": ["python", "algorithms", "debugging", "data_structures", "oop"]
    },
    "math": {
        "target_count": 200,
        "subtopics": ["algebra", "calculus", "statistics", "probability", "linear_algebra", "trigonometry"]
    },
    "physics": {
        "target_count": 150,
        "subtopics": ["mechanics", "thermodynamics", "electromagnetism", "waves", "quantum"]
    },
    "chemistry": {
        "target_count": 150,
        "subtopics": ["organic", "inorganic", "biochemistry", "stoichiometry", "reactions"]
    },
    "biology": {
        "target_count": 150,
        "subtopics": ["molecular", "genetics", "ecology", "anatomy", "evolution"]
    },
    "socratic": {
        "target_count": 150,
        "subtopics": ["hints", "questions", "misconceptions", "scaffolding"]
    }
}


def get_domain_config(domain: str) -> Dict[str, Any]:
    """Get configuration for a specific domain."""
    return DOMAIN_CONFIG.get(domain, {"target_count": 100, "subtopics": ["general"]})
