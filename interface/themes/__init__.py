"""
MITS Theme Module
Claude-style themes for Gradio interface
Feature: 008-claude-ui-redesign
"""

from .claude_dark import claude_dark, ClaudeDark
from .claude_light import claude_light, ClaudeLight


def get_theme(theme_name: str = "dark"):
    """
    Get a theme by name.

    Args:
        theme_name: Theme name - "dark" or "light"

    Returns:
        Gradio theme instance
    """
    themes = {
        "dark": claude_dark,
        "light": claude_light,
    }
    return themes.get(theme_name, claude_dark)


__all__ = [
    "claude_dark",
    "claude_light",
    "ClaudeDark",
    "ClaudeLight",
    "get_theme",
]
