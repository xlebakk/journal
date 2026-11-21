"""Icons of the PWA and the Android app: a ruled page with the red margin and «Ж».

Run once after a design change and commit the PNGs (the font is only needed here):
    uv run --project backend python mobile/scripts/make_icons.py
Colours are the light-theme tokens of frontend/src/shared/ui/tokens.css.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PAPER = (244, 241, 232)
SHEET = (251, 250, 245)
RULE = (218, 212, 197)
RED_PEN = (191, 51, 40)
INK = (27, 33, 48)

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend" / "public" / "icons"
ANDROID_RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"
FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/georgiab.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    sys.exit("No serif bold font found: add one to FONT_CANDIDATES")


def page(size: int, content: float = 1.0, background: tuple[int, int, int] = PAPER) -> Image.Image:
    """`content` < 1 keeps the drawing inside the safe zone of maskable / adaptive icons."""
    scale = 4  # draw large, then downsample: smooth lines without antialiasing tricks
    big = size * scale
    image = Image.new("RGB", (big, big), background)
    draw = ImageDraw.Draw(image)
    inner = int(big * content)
    left = (big - inner) // 2
    top = left
    line = max(scale, inner // 96)
    for i in range(1, 8):
        y = top + inner * i // 8
        draw.rectangle([left, y - line // 2, left + inner, y + line // 2], fill=RULE)
    margin_x = left + int(inner * 0.24)
    draw.rectangle([margin_x - line, top, margin_x + line, top + inner], fill=RED_PEN)
    glyph = font(int(inner * 0.5))
    box = draw.textbbox((0, 0), "Ж", font=glyph)
    width, height = box[2] - box[0], box[3] - box[1]
    x = margin_x + (left + inner - margin_x - width) // 2 - box[0] + int(inner * 0.02)
    y = top + (inner - height) // 2 - box[1]
    draw.text((x, y), "Ж", font=glyph, fill=INK)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)
    print(path.relative_to(ROOT))


def web() -> None:
    save(page(192), WEB / "icon-192.png")
    save(page(512), WEB / "icon-512.png")
    save(page(512, content=0.7), WEB / "maskable-512.png")
    save(page(180), WEB / "apple-touch-icon.png")
    save(page(32), WEB / "favicon-32.png")


# Launcher icons: legacy (48 dp) and adaptive foreground (108 dp, 72 dp safe zone).
DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}


def android() -> None:
    if not ANDROID_RES.exists():
        sys.exit("mobile/android does not exist yet: run `npx cap add android` first")
    for name, factor in DENSITIES.items():
        folder = ANDROID_RES / f"mipmap-{name}"
        legacy = page(round(48 * factor))
        save(legacy, folder / "ic_launcher.png")
        round_icon = legacy.copy()
        mask = Image.new("L", round_icon.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, *round_icon.size], fill=255)
        circle = Image.new("RGB", round_icon.size, PAPER)
        circle.paste(round_icon, mask=mask)
        save(circle, folder / "ic_launcher_round.png")
        save(page(round(108 * factor), content=0.62), folder / "ic_launcher_foreground.png")
    # Splash: the paper colour with the icon in the middle (Capacitor's splash drawables).
    for splash in ANDROID_RES.glob("drawable*/splash.png"):
        with Image.open(splash) as old:
            width, height = old.size
        canvas = Image.new("RGB", (width, height), PAPER)
        side = min(width, height) // 3
        canvas.paste(page(side, background=PAPER), ((width - side) // 2, (height - side) // 2))
        save(canvas, splash)


if __name__ == "__main__":
    web()
    if "--android" in sys.argv:
        android()
