// Checks WCAG AA contrast of the design tokens in both themes (SPEC §12).
// Run: npm run contrast. Exits with code 1 on any failure.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const TOKENS = fileURLToPath(new URL("../src/shared/ui/tokens.css", import.meta.url));
const css = readFileSync(TOKENS, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

function block(selector) {
  const start = css.indexOf(selector);
  if (start === -1) throw new Error(`Selector not found: ${selector}`);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  const vars = {};
  for (const [, name, value] of css.slice(open + 1, close).matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    vars[name] = value.trim();
  }
  return vars;
}

function parseColor(value) {
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 };
  }
  const rgb = value.match(/^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*(?:\/\s*([\d.]+)%)?\s*\)$/);
  if (rgb) {
    return { r: +rgb[1], g: +rgb[2], b: +rgb[3], a: rgb[4] === undefined ? 1 : +rgb[4] / 100 };
  }
  throw new Error(`Unsupported colour: ${value}`);
}

function over(fg, bg) {
  const mix = (f, b) => f * fg.a + b * (1 - fg.a);
  return { r: mix(fg.r, bg.r), g: mix(fg.g, bg.g), b: mix(fg.b, bg.b), a: 1 };
}

function luminance({ r, g, b }) {
  const channel = (c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// [foreground, background, background-is-laid-over, minimum ratio, what it is]
const TEXT = 4.5;
const PAIRS = [
  ["ink", "paper", null, TEXT, "body text"],
  ["ink", "sheet", null, TEXT, "table text"],
  ["ink-2", "paper", null, TEXT, "secondary text"],
  ["ink-2", "sheet", null, TEXT, "captions in tables"],
  ["accent", "paper", null, TEXT, "links"],
  ["accent", "sheet", null, TEXT, "links in tables, focus"],
  ["red-pen", "paper", null, TEXT, "errors"],
  ["red-pen", "sheet", null, TEXT, "«н», low grades"],
  ["pencil", "sheet", null, TEXT, "«оп», warnings"],
  ["on-accent", "accent", null, TEXT, "primary button"],
  ["accent", "accent-soft", "sheet", TEXT, "active menu item, chips"],
  ["accent-strong", "sheet", null, TEXT, "links on hover"],
  ["green", "sheet", null, TEXT, "«был», paid"],
  ["ink", "accent-tint", null, TEXT, "table headers"],
  ["ink", "accent-soft", null, TEXT, "the chosen group, the profile block"],
  ["ink-2", "sheet-2", null, TEXT, "captions on light panels"],
  ["accent", "marker-soft", null, TEXT, "links in today's column"],
  ["ink", "rule", null, 3, "borders against text are decorative; text on a rule fill"],
  ["ink", "marker", "sheet", TEXT, "today header, search hit"],
  ["ink", "marker-soft", "sheet", TEXT, "grade in today column"],
  ["red-pen", "marker-soft", "sheet", TEXT, "«н» in today column"],
  ["pencil", "marker-soft", "sheet", TEXT, "«оп» in today column"],
  ...[1, 2, 3, 4, 5, 6].map((i) => [`stamp-${i}`, `stamp-${i}@10`, "paper", TEXT, "initials"]),
];

function resolve(vars, name, base) {
  const [token, tint] = name.split("@");
  let color = parseColor(vars[token]);
  if (tint) color = { ...color, a: +tint / 100 };
  return color.a < 1 ? over(color, parseColor(vars[base])) : color;
}

const light = block(":root {");
const darkMedia = block(':root:not([data-theme="light"]) {');
const dark = { ...light, ...block(':root[data-theme="dark"] {') };
let failed = false;

if (JSON.stringify(darkMedia) !== JSON.stringify(block(':root[data-theme="dark"] {'))) {
  console.error("✗ dark tokens differ between @media and [data-theme=dark] blocks");
  failed = true;
}

for (const [theme, vars] of [
  ["light", light],
  ["dark", dark],
]) {
  for (const [fg, bg, base, min, what] of PAIRS) {
    const r = ratio(resolve(vars, fg, base), resolve(vars, bg, base));
    const ok = r >= min;
    failed ||= !ok;
    const line = `${ok ? "✓" : "✗"} ${theme.padEnd(5)} ${fg} on ${bg}`.padEnd(46);
    console[ok ? "log" : "error"](`${line} ${r.toFixed(2).padStart(5)} (min ${min}) ${what}`);
  }
}

process.exit(failed ? 1 : 0);
