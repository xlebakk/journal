import { brandPalette, contrast, parseHex } from "./brand";

const rgb = (hex: string) => parseHex(hex)!;

describe("brandPalette", () => {
  it.each(["#2b67c6", "#ffeb3b", "#f5f5f5", "#000000", "#1f7a5c", "#e91e63"])(
    "keeps links and buttons readable for %s",
    (color) => {
      const p = brandPalette(color)!;
      expect(contrast(rgb(p["--brand-accent"]!), rgb("#ffffff"))).toBeGreaterThanOrEqual(4.5);
      expect(contrast(rgb(p["--brand-dark-accent"]!), rgb("#171d27"))).toBeGreaterThanOrEqual(4.5);
      expect(
        contrast(rgb(p["--brand-night-accent"]!), rgb(p["--brand-night-1"]!)),
      ).toBeGreaterThanOrEqual(4.5);
      expect(contrast(rgb("#f2f6ff"), rgb(p["--brand-night-1"]!))).toBeGreaterThanOrEqual(4.5);
      expect(contrast(rgb("#1f2a37"), rgb(p["--brand-accent-tint"]!))).toBeGreaterThanOrEqual(4.5);
    },
  );

  it("refuses anything but #rrggbb", () => {
    expect(brandPalette("red")).toBeNull();
    expect(brandPalette("#fff")).toBeNull();
  });
});
