import { useCallback, useEffect, useRef, useState } from "react";

// What counts as the user being at this tab: a click or tap, a key, a scroll. Moving the pointer
// does not (it drifts over a window nobody is reading).
const ACTIVITY = ["pointerdown", "keydown", "wheel", "touchstart"] as const;

/** Whether this tab has had no input for `thresholdMs` (0: never idle, e.g. while the setting is
 *  unknown). Any input, or `reset()`, ends idle and starts the wait again. */
export function useIdle(thresholdMs: number): { idle: boolean; reset(): void } {
  const [idle, setIdle] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  /** Start the wait again. */
  const arm = useCallback(() => {
    clearTimeout(timer.current);
    if (thresholdMs > 0) timer.current = setTimeout(() => setIdle(true), thresholdMs);
  }, [thresholdMs]);
  const reset = useCallback(() => {
    setIdle(false);
    arm();
  }, [arm]);

  useEffect(() => {
    arm();
    const opts = { capture: true, passive: true } as const;
    for (const e of ACTIVITY) window.addEventListener(e, reset, opts);
    return () => {
      clearTimeout(timer.current);
      for (const e of ACTIVITY) window.removeEventListener(e, reset, opts);
    };
  }, [arm, reset]);

  return { idle, reset };
}
