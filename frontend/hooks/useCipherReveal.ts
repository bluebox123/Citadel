"use client";

import { useState, useEffect, useRef } from "react";

const HEX = "0123456789abcdef";

// Randomise one hex character
function randHex(): string {
  return HEX[Math.floor(Math.random() * 16)];
}

/**
 * Returns a string that starts as random hex noise and progressively locks
 * characters left-to-right until the full target is revealed, simulating
 * a cipher being cracked in real time.
 *
 * @param target  The final string to reveal (64-char hex)
 * @param active  Rising edge triggers the animation; false resets to dots
 */
export function useCipherReveal(target: string, active: boolean): string {
  const len = target.length;
  const [chars, setChars] = useState<string[]>(() => Array(len).fill("·"));
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedRef = useRef(0);

  useEffect(() => {
    // Clear any running animation
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!active) {
      elapsedRef.current = 0;
      setChars(Array(len).fill("·"));
      return;
    }

    elapsedRef.current = 0;

    // Phase 1 (0–120ms): all chars scramble simultaneously
    // Phase 2 (120ms+):  lock chars from left @ 14ms each
    const TICK_MS = 28;
    const SCRAMBLE_MS = 120;
    const LOCK_EACH_MS = 14;

    intervalRef.current = setInterval(() => {
      elapsedRef.current += TICK_MS;
      const elapsed = elapsedRef.current;

      setChars(
        target.split("").map((actual, i) => {
          const lockAt = SCRAMBLE_MS + i * LOCK_EACH_MS;
          if (elapsed >= lockAt) return actual;
          return randHex();
        })
      );

      const done = SCRAMBLE_MS + len * LOCK_EACH_MS + TICK_MS;
      if (elapsed >= done) {
        clearInterval(intervalRef.current!);
        intervalRef.current = null;
        setChars(target.split(""));
      }
    }, TICK_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [target, active, len]);

  return chars.join("");
}
