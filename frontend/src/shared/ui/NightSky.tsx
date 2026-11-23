import styles from "./NightSky.module.css";

// Star positions in the 1000 × 1000 box: few and faint, no sparkle.
const STARS: [number, number, number][] = [
  [62, 88, 1.3], [138, 212, 0.9], [205, 64, 1.1], [262, 158, 0.8], [318, 96, 1.4],
  [384, 228, 0.9], [452, 72, 1.0], [506, 168, 0.8], [571, 112, 1.2], [733, 74, 0.9],
  [792, 186, 1.1], [858, 98, 0.8], [912, 214, 1.3], [966, 132, 0.9], [44, 318, 0.8],
  [172, 372, 1.0], [296, 298, 0.8], [418, 352, 1.1], [868, 322, 0.9], [948, 402, 0.8],
  [112, 452, 0.7], [352, 436, 0.8], [902, 470, 0.7], [688, 236, 0.8], [232, 488, 0.7],
]; // prettier-ignore

/**
 * The «живые обои» of the login page (stage 19): a quiet night — a deep blue sky, a few faint
 * stars that slowly breathe, a thin moon, three ridges of mountains and mist drifting between
 * them, a still lake without glare. Drawn here, not a video: no extra requests, no licences, CSP stays strict.
 * Motion stops for people who ask the system for less of it.
 */
export function NightSky({ className }: { className?: string }) {
  return (
    <svg
      className={[styles.sky, className].filter(Boolean).join(" ")}
      viewBox="0 0 1000 1000"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id="night-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" className={styles.stopHigh} />
          <stop offset="0.55" className={styles.stopMid} />
          <stop offset="0.82" className={styles.stopLow} />
        </linearGradient>
        <radialGradient id="night-moon-halo">
          <stop offset="0" className={styles.haloInner} />
          <stop offset="1" className={styles.haloOuter} />
        </radialGradient>
        <mask id="night-crescent">
          <rect width="1000" height="1000" className={styles.maskShow} />
          <circle cx="712" cy="314" r="46" className={styles.maskHide} />
        </mask>
        <filter id="night-mist-blur" x="-20%" y="-50%" width="140%" height="200%">
          <feGaussianBlur stdDeviation="22" />
        </filter>
      </defs>

      <rect width="1000" height="1000" fill="url(#night-sky)" />

      <g className={styles.stars}>
        {STARS.map(([x, y, r], i) => (
          <circle
            key={`${x}-${y}`}
            cx={x}
            cy={y}
            r={r}
            className={styles[`twinkle${(i % 4) + 1}`]}
          />
        ))}
      </g>

      <circle cx="700" cy="320" r="150" fill="url(#night-moon-halo)" />
      <circle cx="700" cy="320" r="40" className={styles.moon} mask="url(#night-crescent)" />

      <path
        className={styles.ridgeFar}
        d="M0 600 Q80 560 150 585 T300 548 T450 572 T600 530 T760 565 T900 520 T1000 540 V1000 H0 Z"
      />
      <g className={styles.mistSlow} filter="url(#night-mist-blur)">
        <ellipse cx="260" cy="610" rx="300" ry="34" />
        <ellipse cx="780" cy="596" rx="260" ry="28" />
      </g>
      <path
        className={styles.ridgeMid}
        d="M0 690 Q90 650 180 672 T360 640 T540 684 T720 638 T880 676 T1000 650 V1000 H0 Z"
      />
      <g className={styles.mistFast} filter="url(#night-mist-blur)">
        <ellipse cx="420" cy="708" rx="340" ry="30" />
        <ellipse cx="900" cy="716" rx="220" ry="24" />
      </g>
      <path
        className={styles.ridgeNear}
        d="M0 780 Q110 745 220 770 T440 742 T660 782 T880 744 T1000 762 V1000 H0 Z"
      />

      <rect className={styles.lake} x="0" y="858" width="1000" height="142" />
    </svg>
  );
}
