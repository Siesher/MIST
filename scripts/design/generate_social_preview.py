"""Generate GitHub Social Preview image (1280x640) in Frieren aesthetic."""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1280, 640
random.seed(42)

img = Image.new("RGB", (WIDTH, HEIGHT), "#1a1035")
draw = ImageDraw.Draw(img, "RGBA")

# --- Background gradient (vertical bands blended) ---
for x in range(WIDTH):
    t = x / WIDTH
    # Parabolic: darker at edges, lighter purple in center
    factor = 1.0 - 0.4 * (2 * t - 1) ** 2
    r = int(26 + (45 - 26) * factor)
    g = int(16 + (27 - 16) * factor)
    b = int(53 + (105 - 53) * factor)
    draw.line([(x, 0), (x, HEIGHT)], fill=(r, g, b))

# --- Decorative particles ---
for _ in range(80):
    px = random.randint(0, WIDTH)
    py = random.randint(0, HEIGHT)
    pr = random.uniform(1, 3)
    alpha = random.randint(30, 90)
    colors = [(196, 181, 253), (129, 140, 248), (233, 213, 255)]
    c = random.choice(colors)
    draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(*c, alpha))

# --- Magic circles (left) ---
cx_l, cy_l = 180, HEIGHT // 2
for radius in [120, 90, 60]:
    draw.ellipse(
        [cx_l - radius, cy_l - radius, cx_l + radius, cy_l + radius],
        outline=(196, 181, 253, 25),
        width=1,
    )
# Hexagram left
for angle_offset in [0, 180]:
    pts = []
    for i in range(3):
        a = math.radians(angle_offset + 90 + i * 120)
        pts.append((cx_l + 80 * math.cos(a), cy_l + 80 * math.sin(a)))
    draw.polygon(pts, outline=(196, 181, 253, 20))

# --- Magic circles (right) ---
cx_r, cy_r = WIDTH - 180, HEIGHT // 2
for radius in [120, 90, 60]:
    draw.ellipse(
        [cx_r - radius, cy_r - radius, cx_r + radius, cy_r + radius],
        outline=(129, 140, 248, 25),
        width=1,
    )
for angle_offset in [0, 180]:
    pts = []
    for i in range(3):
        a = math.radians(angle_offset + 90 + i * 120)
        pts.append((cx_r + 80 * math.cos(a), cy_r + 80 * math.sin(a)))
    draw.polygon(pts, outline=(129, 140, 248, 20))

# --- Crystal icon (center top) ---
crystal_cx, crystal_cy = WIDTH // 2, 160
diamond_size = 35
pts_diamond = [
    (crystal_cx, crystal_cy - diamond_size),
    (crystal_cx + diamond_size * 0.6, crystal_cy),
    (crystal_cx, crystal_cy + diamond_size),
    (crystal_cx - diamond_size * 0.6, crystal_cy),
]
draw.polygon(pts_diamond, fill=(196, 181, 253, 30), outline=(196, 181, 253, 160))
# Sparkle lines
for angle, length in [(90, 15), (45, 10), (135, 10)]:
    a = math.radians(angle)
    x1 = crystal_cx + (diamond_size + 5) * math.cos(a)
    y1 = crystal_cy - (diamond_size + 5) * math.sin(a)
    x2 = crystal_cx + (diamond_size + 5 + length) * math.cos(a)
    y2 = crystal_cy - (diamond_size + 5 + length) * math.sin(a)
    draw.line([(x1, y1), (x2, y2)], fill=(233, 213, 255, 100), width=1)

# --- Accent line bottom ---
for x in range(WIDTH):
    t = x / WIDTH
    alpha = int(120 * math.sin(t * math.pi))
    draw.line([(x, HEIGHT - 30), (x, HEIGHT - 28)], fill=(196, 181, 253, alpha))


# --- Text ---
# Try to load nice fonts, fallback to default
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        "C:/Windows/Fonts/segoeuil.ttf",  # Segoe UI Light
        "C:/Windows/Fonts/segoeui.ttf",  # Segoe UI
        "C:/Windows/Fonts/arial.ttf",
    ]
    if bold:
        font_candidates = [
            "C:/Windows/Fonts/segoeuib.ttf",  # Segoe UI Bold
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


font_title = load_font(80)
font_subtitle = load_font(22)
font_tagline = load_font(16)
font_desc = load_font(18)
font_badge = load_font(14, bold=True)

# Title: M I T S
title = "M  I  T  S"
bbox = draw.textbbox((0, 0), title, font=font_title)
tw = bbox[2] - bbox[0]
draw.text(
    ((WIDTH - tw) // 2, 220),
    title,
    font=font_title,
    fill=(233, 213, 255),
)

# Subtitle
subtitle = "MATH  INTELLIGENT  TUTORING  SYSTEM"
bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
tw = bbox[2] - bbox[0]
draw.text(
    ((WIDTH - tw) // 2, 320),
    subtitle,
    font=font_subtitle,
    fill=(167, 139, 250),
)

# Description
desc = "Socratic STEM tutor  ·  Multi-Agent Architecture  ·  Qwen3.5-9B Fine-tuned"
bbox = draw.textbbox((0, 0), desc, font=font_desc)
tw = bbox[2] - bbox[0]
draw.text(
    ((WIDTH - tw) // 2, 380),
    desc,
    font=font_desc,
    fill=(196, 181, 253, 180),
)

# Pipeline badges
badges = ["GSPO", "KTO", "DPO"]
badge_colors = [(129, 140, 248), (167, 139, 250), (196, 181, 253)]
badge_w, badge_h = 100, 32
total_badges_w = len(badges) * badge_w + (len(badges) - 1) * 30
start_x = (WIDTH - total_badges_w) // 2

for i, (label, color) in enumerate(zip(badges, badge_colors)):
    bx = start_x + i * (badge_w + 30)
    by = 440
    # Badge background
    draw.rounded_rectangle(
        [bx, by, bx + badge_w, by + badge_h],
        radius=6,
        fill=(*color, 40),
        outline=(*color, 120),
    )
    # Badge text
    bbox = draw.textbbox((0, 0), label, font=font_badge)
    lw = bbox[2] - bbox[0]
    lh = bbox[3] - bbox[1]
    draw.text(
        (bx + (badge_w - lw) // 2, by + (badge_h - lh) // 2 - 2),
        label,
        font=font_badge,
        fill=(*color, 220),
    )

    # Arrow between badges
    if i < len(badges) - 1:
        arrow_x = bx + badge_w + 5
        arrow_y = by + badge_h // 2
        draw.text((arrow_x, arrow_y - 8), "→", font=font_tagline, fill=(167, 139, 250, 100))

# Tagline at bottom
tagline = "Reinforcement Learning  ·  3-Stage Pipeline  ·  3,678 Eval Problems"
bbox = draw.textbbox((0, 0), tagline, font=font_tagline)
tw = bbox[2] - bbox[0]
draw.text(
    ((WIDTH - tw) // 2, 510),
    tagline,
    font=font_tagline,
    fill=(129, 140, 248, 120),
)

# Footer
footer = "github.com/Siesher/MITS"
bbox = draw.textbbox((0, 0), footer, font=font_tagline)
tw = bbox[2] - bbox[0]
draw.text(
    ((WIDTH - tw) // 2, 570),
    footer,
    font=font_tagline,
    fill=(196, 181, 253, 80),
)

# --- Save ---
output_path = Path(__file__).resolve().parents[2] / "figures" / "social_preview.png"
img.save(output_path, "PNG", quality=95)
print(f"Saved: {output_path} ({img.size[0]}x{img.size[1]})")
