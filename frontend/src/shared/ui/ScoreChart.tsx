import styles from "./ScoreChart.module.css";

export type ScorePoint = {
  key: string;
  /** Short caption under the point (a date). */
  label: string;
  /** Result in % of the maximum; null — absent. */
  percent: number | null;
  /** What is written above the point: «24 / 30». */
  score: string;
};

const W = 640;
const H = 220;
const PAD = { top: 24, right: 16, bottom: 28, left: 36 };
const GRID = [0, 25, 50, 75, 100];
const INSET = 40;

/**
 * Results of mock exams in % (tests may have different maxima), with the goal as a dashed
 * line and the score above every point (decision of stage 5). Plain SVG, colours from tokens.
 */
export function ScoreChart({
  points,
  target,
  targetLabel,
  label,
}: {
  points: ScorePoint[];
  target?: number | null;
  /** «цель 80%» — from the dictionary. */
  targetLabel?: string;
  label: string;
}) {
  const inner = { w: W - PAD.left - PAD.right, h: H - PAD.top - PAD.bottom };
  // Points stay away from the axis and the right edge, so their labels fit on a phone.
  const span = inner.w - 2 * INSET;
  const x = (i: number) =>
    PAD.left + INSET + (points.length <= 1 ? span / 2 : (i * span) / (points.length - 1));
  const y = (pct: number) => PAD.top + inner.h - (pct / 100) * inner.h;
  const present = points
    .map((p, i) => ({ ...p, i }))
    .filter((p): p is ScorePoint & { i: number; percent: number } => p.percent !== null);
  const path = present.map((p) => `${x(p.i)},${y(p.percent)}`).join(" ");
  return (
    <svg className={styles.chart} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      {GRID.map((g) => (
        <g key={g}>
          <line className={styles.grid} x1={PAD.left} x2={W - PAD.right} y1={y(g)} y2={y(g)} />
          <text className={styles.axis} x={PAD.left - 6} y={y(g) + 4} textAnchor="end">
            {g}%
          </text>
        </g>
      ))}
      {target != null && (
        <g>
          <line
            className={styles.target}
            x1={PAD.left}
            x2={W - PAD.right}
            y1={y(target)}
            y2={y(target)}
          />
          <text className={styles.targetLabel} x={W - PAD.right} y={y(target) - 4} textAnchor="end">
            {targetLabel}
          </text>
        </g>
      )}
      {present.length > 1 && <polyline className={styles.line} points={path} />}
      {points.map((p, i) => (
        <g key={p.key}>
          {p.percent === null ? (
            <text className={styles.absent} x={x(i)} y={y(0) - 4} textAnchor="middle">
              {p.score}
            </text>
          ) : (
            <>
              <circle className={styles.dot} cx={x(i)} cy={y(p.percent)} r={3.5} />
              <text className={styles.score} x={x(i)} y={y(p.percent) - 8} textAnchor="middle">
                {p.score}
              </text>
            </>
          )}
          <text className={styles.axis} x={x(i)} y={H - 8} textAnchor="middle">
            {p.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
