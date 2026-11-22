"""Icons of the PWA and the Android app: the Daftar mark — a journal page with a margin line,
ruled lines and a red bookmark — on the blue of the interface.

Run once after a design change and commit the PNGs:
    uv run --project backend python mobile/scripts/make_icons.py [--android]
The geometry is the one of frontend/src/shared/ui/Logo.tsx (viewBox 32×32); colours are the
light-theme tokens of frontend/src/shared/ui/tokens.css.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

PAPER = (255, 255, 255)  # --paper
ACCENT = (43, 103, 198)  # --accent
TINT = (214, 232, 250)  # --accent-tint
RED_PEN = (194, 54, 44)  # --red-pen

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend" / "public" / "icons"
ANDROID_RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"


def mark(
    size: int, content: float = 1.0, background: tuple[int, int, int] = ACCENT
) -> Image.Image:
    """`content` < 1 keeps the drawing inside the safe zone of maskable / adaptive icons."""
    scale = 4  # draw large, then downsample: smooth edges without antialiasing tricks
    big = size * scale
    image = Image.new("RGB", (big, big), background)
    draw = ImageDraw.Draw(image)
    # Logo.tsx units → pixels: the page (21×25 units) is centred and fills `content` of 32.
    unit = big * content / 32
    offset = (big - 32 * unit) / 2

    def at(x: float, y: float) -> tuple[float, float]:
        return offset + x * unit, offset + y * unit

    draw.rounded_rectangle(
        [*at(5.5, 3.5), *at(26.5, 28.5)], radius=3 * unit, fill=PAPER
    )
    margin = 1.2 * unit
    draw.rectangle(
        [
            at(11, 4)[0] - margin / 2,
            at(11, 4)[1],
            at(11, 4)[0] + margin / 2,
            at(11, 28)[1],
        ],
        fill=ACCENT,
    )
    rule = 1.6 * unit
    for y, end in ((13, 23), (18, 23), (23, 20)):
        left, top = at(14, y)
        right, _ = at(end, y)
        draw.rounded_rectangle(
            [left, top - rule / 2, right, top + rule / 2], radius=rule / 2, fill=TINT
        )
    draw.polygon(
        [at(19.5, 3.5), at(24, 3.5), at(24, 12), at(21.75, 10.2), at(19.5, 12)],
        fill=RED_PEN,
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)
    print(path.relative_to(ROOT))


def web() -> None:
    save(mark(192), WEB / "icon-192.png")
    save(mark(512), WEB / "icon-512.png")
    save(mark(512, content=0.72), WEB / "maskable-512.png")
    save(mark(180), WEB / "apple-touch-icon.png")
    save(mark(32, content=1.12), WEB / "favicon-32.png")


# Launcher icons: legacy (48 dp) and adaptive foreground (108 dp, 72 dp safe zone).
DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}


def android() -> None:
    if not ANDROID_RES.exists():
        sys.exit("mobile/android does not exist yet: run `npx cap add android` first")
    for name, factor in DENSITIES.items():
        folder = ANDROID_RES / f"mipmap-{name}"
        legacy = mark(round(48 * factor))
        save(legacy, folder / "ic_launcher.png")
        round_icon = legacy.copy()
        mask = Image.new("L", round_icon.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, *round_icon.size], fill=255)
        circle = Image.new("RGB", round_icon.size, PAPER)
        circle.paste(round_icon, mask=mask)
        save(circle, folder / "ic_launcher_round.png")
        save(
            mark(round(108 * factor), content=0.62),
            folder / "ic_launcher_foreground.png",
        )
    # Splash: white with the icon in the middle (Capacitor's splash drawables).
    for splash in ANDROID_RES.glob("drawable*/splash.png"):
        with Image.open(splash) as old:
            width, height = old.size
        canvas = Image.new("RGB", (width, height), PAPER)
        side = min(width, height) // 3
        canvas.paste(mark(side), ((width - side) // 2, (height - side) // 2))
        save(canvas, splash)


if __name__ == "__main__":
    web()
    if "--android" in sys.argv:
        android()
