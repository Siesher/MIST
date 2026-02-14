"""
Claude-Style Light Theme for MITS
Based on Claude Desktop aesthetic
Feature: 008-claude-ui-redesign
"""

import gradio as gr
from gradio.themes.base import Base
from gradio.themes.utils import colors, fonts, sizes


class ClaudeLight(Base):
    """Light theme inspired by Claude Desktop interface."""

    def __init__(
        self,
        *,
        primary_hue: colors.Color = colors.emerald,
        secondary_hue: colors.Color = colors.gray,
        neutral_hue: colors.Color = colors.gray,
        spacing_size: sizes.Size = sizes.spacing_md,
        radius_size: sizes.Size = sizes.radius_lg,
        text_size: sizes.Size = sizes.text_md,
        font: fonts.Font | str = (
            fonts.GoogleFont("Inter"),
            "ui-sans-serif",
            "system-ui",
            "sans-serif",
        ),
        font_mono: fonts.Font | str = (
            fonts.GoogleFont("JetBrains Mono"),
            "ui-monospace",
            "Consolas",
            "monospace",
        ),
    ):
        super().__init__(
            primary_hue=primary_hue,
            secondary_hue=secondary_hue,
            neutral_hue=neutral_hue,
            spacing_size=spacing_size,
            radius_size=radius_size,
            text_size=text_size,
            font=font,
            font_mono=font_mono,
        )

        # Core colors
        self.set(
            # Background colors
            body_background_fill="#ffffff",
            body_background_fill_dark="#ffffff",
            background_fill_primary="#ffffff",
            background_fill_primary_dark="#ffffff",
            background_fill_secondary="#f5f5f5",
            background_fill_secondary_dark="#f5f5f5",

            # Text colors
            body_text_color="#1a1a1a",
            body_text_color_dark="#1a1a1a",
            body_text_color_subdued="#666666",
            body_text_color_subdued_dark="#666666",

            # Border colors
            border_color_primary="#d0d0d0",
            border_color_primary_dark="#d0d0d0",
            border_color_accent="#10a37f",
            border_color_accent_dark="#10a37f",

            # Button colors
            button_primary_background_fill="#10a37f",
            button_primary_background_fill_dark="#10a37f",
            button_primary_background_fill_hover="#0d8a6a",
            button_primary_background_fill_hover_dark="#0d8a6a",
            button_primary_text_color="white",
            button_primary_text_color_dark="white",
            button_secondary_background_fill="#e8e8e8",
            button_secondary_background_fill_dark="#e8e8e8",
            button_secondary_text_color="#1a1a1a",
            button_secondary_text_color_dark="#1a1a1a",

            # Input colors
            input_background_fill="#e8e8e8",
            input_background_fill_dark="#e8e8e8",
            input_border_color="#d0d0d0",
            input_border_color_dark="#d0d0d0",
            input_border_color_focus="#10a37f",
            input_border_color_focus_dark="#10a37f",
            input_placeholder_color="#666666",
            input_placeholder_color_dark="#666666",

            # Block colors
            block_background_fill="#f5f5f5",
            block_background_fill_dark="#f5f5f5",
            block_border_color="#d0d0d0",
            block_border_color_dark="#d0d0d0",
            block_label_background_fill="#f5f5f5",
            block_label_background_fill_dark="#f5f5f5",
            block_label_text_color="#1a1a1a",
            block_label_text_color_dark="#1a1a1a",
            block_title_text_color="#1a1a1a",
            block_title_text_color_dark="#1a1a1a",

            # Panel colors
            panel_background_fill="#f5f5f5",
            panel_background_fill_dark="#f5f5f5",
            panel_border_color="#d0d0d0",
            panel_border_color_dark="#d0d0d0",

            # Table colors
            table_border_color="#d0d0d0",
            table_border_color_dark="#d0d0d0",
            table_even_background_fill="#f5f5f5",
            table_even_background_fill_dark="#f5f5f5",
            table_odd_background_fill="#ffffff",
            table_odd_background_fill_dark="#ffffff",
            table_row_focus="#e8e8e8",
            table_row_focus_dark="#e8e8e8",

            # Checkbox/Radio colors
            checkbox_background_color="#e8e8e8",
            checkbox_background_color_dark="#e8e8e8",
            checkbox_background_color_selected="#10a37f",
            checkbox_background_color_selected_dark="#10a37f",
            checkbox_border_color="#d0d0d0",
            checkbox_border_color_dark="#d0d0d0",
            checkbox_border_color_selected="#10a37f",
            checkbox_border_color_selected_dark="#10a37f",

            # Slider colors
            slider_color="#10a37f",
            slider_color_dark="#10a37f",

            # Shadow
            shadow_drop="0 2px 8px rgba(0, 0, 0, 0.1)",
            shadow_drop_lg="0 4px 16px rgba(0, 0, 0, 0.15)",
        )


# Create singleton instance
claude_light = ClaudeLight()
