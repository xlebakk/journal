/**
 * Stage 19: the center picks one colour in the settings and the whole interface follows it.
 * From that colour come the accent, its strong and pale shades, the markers and the night of
 * the login page — for the light and the dark theme. Text contrast is kept by construction:
 * the accent is darkened (light theme) or lightened (dark theme) until WCAG AA holds.
 * The values go to `--brand-*` custom properties that tokens.css reads with its own defaults.
 */

type Rgb = [number, number, number];

const WHITE: Rgb = [255, 255, 255];
const BLACK: Rgb = [0, 0, 0];
// Surfaces of tokens.css the accent is read on.
const LIGHT_SHEET: Rgb = [255, 255, 255];
const DARK_SHEET: Rgb = [23, 29, 39];
const AA = 4.6; // a little above 4.5, for rounding

export function parseHex(hex: string): Rgb | null {
  const match = /^#([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return null;
  const n = parseInt(match[1]!, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const toHex = (c: Rgb) => `#${c.map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;

/** `amount` of `b` mixed into `a`. */
const mix = (a: Rgb, b: Rgb, amount: number): Rgb =>
  a.map((v, i) => v + (b[i]! - v) * amount) as Rgb;

function luminance(c: Rgb): number {
  const [r, g, b] = c.map((v) => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as Rgb;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** Moves `color` towards `towards` in small steps until it reads on `on`. */
function readable(color: Rgb, on: Rgb, towards: Rgb): Rgb {
  let current = color;
  for (let step = 0; step < 40 && contrast(current, on) < AA; step += 1) {
    current = mix(current, towards, 0.06);
  }
  return current;
}

export function brandPalette(hex: string): Record<string, string> | null {
  const base = parseHex(hex);
  if (!base) return null;
  const light = readable(base, LIGHT_SHEET, BLACK);
  const dark = readable(base, DARK_SHEET, WHITE);
  const night = mix(base, BLACK, 0.8);
  return {
    "--brand-accent": toHex(light),
    "--brand-accent-strong": toHex(mix(light, BLACK, 0.25)),
    "--brand-accent-soft": toHex(mix(base, WHITE, 0.93)),
    "--brand-accent-tint": toHex(mix(base, WHITE, 0.82)),
    "--brand-marker": toHex(mix(base, WHITE, 0.86)),
    "--brand-marker-soft": toHex(mix(base, WHITE, 0.95)),
    "--brand-dark-accent": toHex(dark),
    "--brand-dark-accent-strong": toHex(mix(dark, WHITE, 0.35)),
    "--brand-dark-accent-soft": toHex(mix(DARK_SHEET, base, 0.14)),
    "--brand-dark-accent-tint": toHex(mix(DARK_SHEET, base, 0.22)),
    "--brand-dark-marker": toHex(mix(DARK_SHEET, base, 0.2)),
    "--brand-dark-marker-soft": toHex(mix(DARK_SHEET, base, 0.1)),
    "--brand-night-1": toHex(night),
    "--brand-night-2": toHex(mix(base, BLACK, 0.65)),
    "--brand-night-accent": toHex(readable(mix(base, WHITE, 0.45), night, WHITE)),
  };
}

/** Sets the palette on <html>: CSSOM, not a style attribute, so the CSP stays strict. */
export function applyBrand(hex: string | undefined): void {
  const palette = hex ? brandPalette(hex) : null;
  if (!palette) return;
  const root = document.documentElement.style;
  for (const [name, value] of Object.entries(palette)) root.setProperty(name, value);
}
