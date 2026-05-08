import { useEffect, useRef, useCallback } from "react";

interface PollingOptions {
  /** Interval in milliseconds. Default: 3000 */
  interval?: number;
  /** Whether polling is enabled. Default: true */
  enabled?: boolean;
  /** Stop polling once this returns true */
  stopWhen?: () => boolean;
}

/**
 * Repeatedly calls `fn` every `interval` ms while the component is mounted
 * and `enabled` is true. Clears the interval when `stopWhen()` returns true.
 */
export function usePolling(fn: () => void, options: PollingOptions = {}) {
  const { interval = 3000, enabled = true, stopWhen } = options;

  const fnRef = useRef(fn);
  fnRef.current = fn;

  const stopWhenRef = useRef(stopWhen);
  stopWhenRef.current = stopWhen;

  const clear = useCallback(() => {
    // handled by cleanup below
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const tick = () => {
      fnRef.current();
      if (stopWhenRef.current?.()) {
        clearInterval(id);
      }
    };

    const id = setInterval(tick, interval);
    return () => clearInterval(id);
  }, [enabled, interval]);

  return { stop: clear };
}
