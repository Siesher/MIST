"""
Claude Desktop Dark Theme for MITS
Feature: 008-claude-ui-redesign
"""

from gradio.themes.base import Base
from gradio.themes.utils import colors, fonts, sizes


class ClaudeDark(Base):
    """Dark theme matching Claude Desktop aesthetic."""

    def __init__(self):
        super().__init__(
            primary_hue=colors.orange,
            secondary_hue=colors.neutral,
            neutral_hue=colors.neutral,
            spacing_size=sizes.spacing_md,
            radius_size=sizes.radius_lg,
            text_size=sizes.text_md,
            font=(
                fonts.GoogleFont("Inter"),
                "ui-sans-serif",
                "-apple-system",
                "system-ui",
                "sans-serif",
            ),
            font_mono=(
                fonts.GoogleFont("JetBrains Mono"),
                "ui-monospace",
                "SFMono-Regular",
                "Consolas",
                "monospace",
            ),
        )

        # Claude Desktop color palette
        self.set(
            # Main backgrounds
            body_background_fill="#212121",
            body_background_fill_dark="#212121",
            background_fill_primary="#212121",
            background_fill_primary_dark="#212121",
            background_fill_secondary="#2f2f2f",
            background_fill_secondary_dark="#2f2f2f",

            # Text
            body_text_color="#ececec",
            body_text_color_dark="#ececec",
            body_text_color_subdued="#a0a0a0",
            body_text_color_subdued_dark="#a0a0a0",

            # Borders
            border_color_primary="#3a3a3a",
            border_color_primary_dark="#3a3a3a",
            border_color_accent="#d97706",
            border_color_accent_dark="#d97706",

            # Primary buttons (orange accent)
            button_primary_background_fill="#d97706",
            button_primary_background_fill_dark="#d97706",
            button_primary_background_fill_hover="#b45309",
            button_primary_background_fill_hover_dark="#b45309",
            button_primary_text_color="#ffffff",
            button_primary_text_color_dark="#ffffff",

            # Secondary buttons
            button_secondary_background_fill="#2f2f2f",
            button_secondary_background_fill_dark="#2f2f2f",
            button_secondary_background_fill_hover="#3a3a3a",
            button_secondary_background_fill_hover_dark="#3a3a3a",
            button_secondary_text_color="#ececec",
            button_secondary_text_color_dark="#ececec",

            # Inputs
            input_background_fill="#2f2f2f",
            input_background_fill_dark="#2f2f2f",
            input_border_color="#3a3a3a",
            input_border_color_dark="#3a3a3a",
            input_border_color_focus="#d97706",
            input_border_color_focus_dark="#d97706",
            input_placeholder_color="#6b6b6b",
            input_placeholder_color_dark="#6b6b6b",

            # Blocks
            block_background_fill="#212121",
            block_background_fill_dark="#212121",
            block_border_color="#2a2a2a",
            block_border_color_dark="#2a2a2a",
            block_label_background_fill="#212121",
            block_label_background_fill_dark="#212121",
            block_label_text_color="#a0a0a0",
            block_label_text_color_dark="#a0a0a0",
            block_title_text_color="#ececec",
            block_title_text_color_dark="#ececec",

            # Panels
            panel_background_fill="#171717",
            panel_background_fill_dark="#171717",
            panel_border_color="#2a2a2a",
            panel_border_color_dark="#2a2a2a",

            # Tables
            table_border_color="#3a3a3a",
            table_border_color_dark="#3a3a3a",
            table_even_background_fill="#2f2f2f",
            table_even_background_fill_dark="#2f2f2f",
            table_odd_background_fill="#212121",
            table_odd_background_fill_dark="#212121",
            table_row_focus="#3a3a3a",
            table_row_focus_dark="#3a3a3a",

            # Checkboxes
            checkbox_background_color="#2f2f2f",
            checkbox_background_color_dark="#2f2f2f",
            checkbox_background_color_selected="#d97706",
            checkbox_background_color_selected_dark="#d97706",
            checkbox_border_color="#3a3a3a",
            checkbox_border_color_dark="#3a3a3a",
            checkbox_border_color_selected="#d97706",
            checkbox_border_color_selected_dark="#d97706",

            # Sliders
            slider_color="#d97706",
            slider_color_dark="#d97706",

            # Shadows
            shadow_drop="0 2px 8px rgba(0, 0, 0, 0.4)",
            shadow_drop_lg="0 4px 16px rgba(0, 0, 0, 0.5)",
        )


# Singleton
claude_dark = ClaudeDark()
