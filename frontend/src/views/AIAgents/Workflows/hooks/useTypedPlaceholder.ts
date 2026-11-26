import { useEffect, useState } from "react";

const TYPE_MS = 38;
const DELETE_MS = 16;
const HOLD_MS = 2200;
const BLINK_MS = 500;
const START_DELAY_MS = 400;

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const randomIndex = (count: number, not: number) => {
  if (count <= 1) return 0;
  let next = Math.floor(Math.random() * count);
  if (next === not) next = (next + 1) % count;
  return next;
};

/**
 * A placeholder that types one of `phrases` like a person would, holds it, deletes
 * it and types another, chosen at random. Paused (and reset) while `active` is false,
 * so it only runs when the field is empty. Under reduced motion it shows a whole
 * phrase and swaps it on each hold instead of typing.
 */
export function useTypedPlaceholder(phrases: readonly string[], active: boolean): string {
  const [text, setText] = useState("");

  useEffect(() => {
    if (!active || phrases.length === 0) {
      setText("");
      return;
    }
    let index = randomIndex(phrases.length, -1);
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const schedule = (fn: () => void, ms: number) => {
      timer = setTimeout(() => {
        if (!cancelled) fn();
      }, ms);
    };

    if (prefersReducedMotion()) {
      const swap = () => {
        setText(phrases[index]);
        index = randomIndex(phrases.length, index);
        schedule(swap, HOLD_MS * 2);
      };
      swap();
      return () => {
        cancelled = true;
        if (timer) clearTimeout(timer);
      };
    }

    const typeChar = (shown: number) => {
      const phrase = phrases[index];
      setText(`${phrase.slice(0, shown)}|`);
      if (shown < phrase.length) {
        // A little unevenness reads as a person typing, not a metronome.
        schedule(() => typeChar(shown + 1), TYPE_MS + Math.random() * 40);
      } else {
        hold(phrase, 0);
      }
    };
    const hold = (phrase: string, blinks: number) => {
      setText(blinks % 2 === 0 ? phrase : `${phrase}|`);
      if (blinks * BLINK_MS < HOLD_MS) schedule(() => hold(phrase, blinks + 1), BLINK_MS);
      else deleteChar(phrase.length);
    };
    const deleteChar = (shown: number) => {
      const phrase = phrases[index];
      setText(`${phrase.slice(0, shown)}|`);
      if (shown > 0) {
        schedule(() => deleteChar(shown - 1), DELETE_MS);
      } else {
        index = randomIndex(phrases.length, index);
        schedule(() => typeChar(0), START_DELAY_MS);
      }
    };

    schedule(() => typeChar(0), START_DELAY_MS);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [active, phrases]);

  return text;
}
