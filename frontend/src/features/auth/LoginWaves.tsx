import { useEffect, useRef } from "react";

import { useMediaQuery } from "@/shared/lib/useMediaQuery";

import { BACK_WAVE, FRONT_WAVE, wavePath } from "./waves";

/**
 * The two corner waves of the login page, alive: their crests travel along the slope like
 * water, redrawn on every animation frame (the browser pauses it in a hidden tab). The shape is
 * set as an attribute of the path, not a style, so the CSP stays strict. Still for people who
 * ask the system for less motion.
 */
export function LoginWaves({
  className,
  backClassName,
  frontClassName,
}: {
  className?: string;
  backClassName?: string;
  frontClassName?: string;
}) {
  const back = useRef<SVGPathElement>(null);
  const front = useRef<SVGPathElement>(null);
  const still = useMediaQuery("(prefers-reduced-motion: reduce)");

  useEffect(() => {
    if (still) return;
    let frame = 0;
    const draw = (time: number) => {
      const seconds = time / 1000;
      // One crest passes in about 9 s at the back and 6 s at the front, in opposite directions.
      back.current?.setAttribute("d", wavePath(BACK_WAVE, (seconds * 2 * Math.PI) / 9));
      front.current?.setAttribute("d", wavePath(FRONT_WAVE, (-seconds * 2 * Math.PI) / 6));
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [still]);

  return (
    <svg
      className={className}
      viewBox="0 0 600 220"
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <path ref={back} className={backClassName} d={wavePath(BACK_WAVE, 0)} />
      <path ref={front} className={frontClassName} d={wavePath(FRONT_WAVE, 0)} />
    </svg>
  );
}
