/**
 * The corner waves of the login page (stage 19): a rising slope with sine crests that travel
 * along it. `wavePath` draws one moment; `LoginWaves` redraws it on every animation frame.
 */

type Wave = {
  /** Height of the slope at the left and right edge (the box is 600 × 220). */
  from: number;
  to: number;
  amplitude: number;
  wavelength: number;
};

const WIDTH = 600;
const HEIGHT = 220;

/** A smooth path through sampled points (Catmull-Rom as cubic Béziers), closed at the bottom. */
export function wavePath(wave: Wave, phase: number): string {
  const points: [number, number][] = [];
  for (let x = -40; x <= WIDTH + 40; x += 40) {
    const slope = wave.from + ((wave.to - wave.from) * x) / WIDTH;
    // The crests grow towards the right, where the wave is tallest.
    const swell = 0.6 + (0.4 * Math.max(0, x)) / WIDTH;
    const y =
      slope + wave.amplitude * swell * Math.sin((2 * Math.PI * x) / wave.wavelength + phase);
    points.push([x, y]);
  }
  const f = (n: number) => n.toFixed(1);
  let d = `M${f(points[0]![0])} ${f(points[0]![1])}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[i - 1] ?? points[i]!;
    const p1 = points[i]!;
    const p2 = points[i + 1]!;
    const p3 = points[i + 2] ?? p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${f(c1[0]!)} ${f(c1[1]!)} ${f(c2[0]!)} ${f(c2[1]!)} ${f(p2[0])} ${f(p2[1])}`;
  }
  return `${d} V${HEIGHT} H-40 Z`;
}

// Both start under the bottom edge on the left, so the box shows no cut.
export const BACK_WAVE: Wave = { from: 236, to: 40, amplitude: 14, wavelength: 300 };
export const FRONT_WAVE: Wave = { from: 250, to: 95, amplitude: 11, wavelength: 220 };
