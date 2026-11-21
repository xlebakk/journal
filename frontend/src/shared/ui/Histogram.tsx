import styles from "./ScoreChart.module.css";

export type Bucket = { key: string; label: string; count: number };

const W = 640;
const H = 200;
const PAD = { top: 20, right: 8, bottom: 28, left: 8 };

/** Distribution of results: one bar per 10 % band, the count above it. */
export function Histogram({ buckets, label }: { buckets: Bucket[]; label: string }) {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  const inner = { w: W - PAD.left - PAD.right, h: H - PAD.top - PAD.bottom };
  const slot = inner.w / Math.max(1, buckets.length);
  return (
    <svg className={styles.chart} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <line
        className={styles.grid}
        x1={PAD.left}
        x2={W - PAD.right}
        y1={PAD.top + inner.h}
        y2={PAD.top + inner.h}
      />
      {buckets.map((b, i) => {
        const height = (b.count / max) * inner.h;
        const left = PAD.left + i * slot;
        const top = PAD.top + inner.h - height;
        return (
          <g key={b.key}>
            {b.count > 0 && (
              <rect className={styles.bar} x={left + 4} y={top} width={slot - 8} height={height} />
            )}
            <text className={styles.count} x={left + slot / 2} y={top - 4} textAnchor="middle">
              {b.count}
            </text>
            <text className={styles.axis} x={left + slot / 2} y={H - 8} textAnchor="middle">
              {b.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
