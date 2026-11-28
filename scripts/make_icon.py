"""Generate assets/seo-analysis.ico, the icon used by the shortcut launchers.

Run from the repository root:  python scripts/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
BACKGROUND = (28, 50, 41)
CREAM = (240, 244, 223)
BAR_DARK = (127, 176, 105)
BAR_LIGHT = (163, 197, 133)
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def build() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((6, 6, SIZE - 6, SIZE - 6), radius=54, fill=BACKGROUND)

    lens_x, lens_y, radius = 106, 106, 58
    for left, height, colour in ((74, 22, BAR_DARK), (96, 36, BAR_LIGHT), (118, 52, BAR_DARK)):
        draw.rounded_rectangle((left, 132 - height, left + 15, 132), radius=4, fill=colour)

    draw.ellipse((lens_x - radius, lens_y - radius, lens_x + radius, lens_y + radius),
                 outline=CREAM, width=15)
    draw.line((144, 144, 209, 209), fill=CREAM, width=17)
    draw.ellipse((201, 201, 219, 219), fill=CREAM)
    return image


def main() -> int:
    target = Path(__file__).resolve().parent.parent / "assets" / "seo-analysis.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    build().save(target, format="ICO", sizes=SIZES)
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
