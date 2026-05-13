"""Génère l'icône Beatfinder en PNG : barres EQ verticales orange sur fond
noir arrondi. Réminiscent d'un mixer / visualizer audio.

Usage : python scripts/gen_icon.py
Output : packaging/beatfinder.png (256x256), beatfinder-512.png (512x512)
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "packaging"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BG = (10, 10, 11, 255)          # noir profond (--color-bg)
SURFACE = (28, 28, 33, 255)     # gris foncé (--color-surface-2)
ACCENT = (249, 115, 22, 255)    # orange (#f97316, --color-accent)
ACCENT_DIM = (180, 75, 15, 255)  # orange foncé pour ombre/profondeur


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fond carré arrondi (radius = 22% du size)
    radius = int(size * 0.22)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=BG)

    # Pastille accent en haut à droite (subtil signe brand)
    dot_r = max(int(size * 0.04), 6)
    dot_pad = int(size * 0.12)
    draw.ellipse(
        (size - dot_pad - dot_r * 2, dot_pad - dot_r, size - dot_pad, dot_pad + dot_r),
        fill=ACCENT,
    )

    # 5 barres EQ verticales centrées, hauteurs variées
    # Pattern inspiré d'un visualizer audio : grave → bass → mid → high → air
    n_bars = 5
    margin_h = int(size * 0.18)  # marge horizontale
    margin_v_top = int(size * 0.28)
    margin_v_bot = int(size * 0.22)
    avail_w = size - margin_h * 2
    avail_h = size - margin_v_top - margin_v_bot
    gap = int(avail_w / (n_bars * 1.6))
    bar_w = (avail_w - gap * (n_bars - 1)) // n_bars

    # Hauteurs relatives : pattern bell-curve évoquant un drop trap
    heights = [0.55, 0.95, 0.75, 0.45, 0.30]

    for i, h_ratio in enumerate(heights):
        x = margin_h + i * (bar_w + gap)
        h = int(avail_h * h_ratio)
        y_bot = size - margin_v_bot
        y_top = y_bot - h
        # Track gris (toute la hauteur dispo)
        draw.rounded_rectangle(
            (x, size - margin_v_bot - avail_h, x + bar_w, y_bot),
            radius=bar_w // 2,
            fill=SURFACE,
        )
        # Barre orange (rempli proportionnel à h_ratio)
        draw.rounded_rectangle(
            (x, y_top, x + bar_w, y_bot),
            radius=bar_w // 2,
            fill=ACCENT,
        )
        # Petit point lumineux au sommet pour un effet "active"
        cap_r = bar_w // 4
        cx = x + bar_w // 2
        cy = y_top + cap_r // 2
        if cap_r > 1:
            draw.ellipse(
                (cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r),
                fill=(255, 200, 150, 255),
            )

    return img


def main() -> None:
    # 256 = AppImage / GNOME, 512 = fallback, 1024 = source pour .icns macOS
    # (iconutil exige du @2x sur 512 donc 1024).
    for size in (256, 512, 1024):
        img = render(size)
        path = OUT_DIR / (
            "beatfinder.png" if size == 256 else f"beatfinder-{size}.png"
        )
        img.save(path)
        print(f"✓ {path}")


if __name__ == "__main__":
    main()
