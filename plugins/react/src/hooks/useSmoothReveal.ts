import { useEffect, useRef, useState } from "react";

export const REVEAL_CHARS_PER_SECOND = 250;
export const MAX_REVEAL_CHARS_PER_SECOND = 450;
export const MAX_REVEAL_LAG_MS = 2000;
export const DRAIN_MS = 5000;
const LONGEST_WORD = 16;

export interface Reveal {
  text: string;
  live: boolean;
  pos: number;
  drainCps: number | null;
}

const IDLE: Reveal = { text: "", live: false, pos: 0, drainCps: null };

/** The revealed part, cut after the last whole word so half-typed words and markdown flicker less. */
export function visibleText(reveal: Reveal): string {
  const end = Math.floor(reveal.pos);
  if (end >= reveal.text.length && !reveal.live) return reveal.text;
  for (let cut = end; cut >= end - LONGEST_WORD; cut--) {
    if (cut <= 0) return "";
    if (/\s/.test(reveal.text.charAt(cut))) return reveal.text.slice(0, cut);
  }
  return reveal.text.slice(0, end);
}

/**
 * Points the reveal at new text. Live text keeps its place while it still starts with what is
 * shown, else restarts. Saved text finishes a reveal in progress, else shows at once.
 */
export function retarget(prev: Reveal, text: string, live: boolean): Reveal {
  if (prev.text === text && prev.live === live) return prev;
  const continues = text.startsWith(visibleText(prev));
  if (live) return { text, live, pos: continues ? Math.min(prev.pos, text.length) : 0, drainCps: null };
  const revealing = (prev.live || prev.drainCps !== null) && prev.pos > 0;
  if (!continues || !revealing) return { text, live, pos: text.length, drainCps: null };
  const pos = Math.min(prev.pos, text.length);
  const drainCps = prev.drainCps ?? ((text.length - pos) * 1000) / DRAIN_MS;
  return { text, live, pos, drainCps };
}

export function advance(reveal: Reveal, elapsedMs: number): Reveal {
  const backlog = reveal.text.length - reveal.pos;
  if (backlog <= 0) return reveal;
  const catchUp = Math.max(REVEAL_CHARS_PER_SECOND, (backlog * 1000) / MAX_REVEAL_LAG_MS);
  const cps = Math.max(Math.min(MAX_REVEAL_CHARS_PER_SECOND, catchUp), reveal.drainCps ?? 0);
  return { ...reveal, pos: Math.min(reveal.text.length, reveal.pos + (cps * elapsedMs) / 1000) };
}

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;

/** Reveals a streamed reply at a steady pace, then finishes it on the saved reply that replaces it. */
export function useSmoothReveal(text: string, live: boolean): string {
  const reveal = useRef<Reveal>(IDLE);
  reveal.current = retarget(reveal.current, text, live);
  const [, rerender] = useState(0);
  const reduceMotion = prefersReducedMotion();
  const behind = reveal.current.pos < text.length;

  useEffect(() => {
    if (!behind || reduceMotion) return;
    let last = performance.now();
    // The loop never stops itself: text may grow in the same render that would have stopped it.
    let frame = requestAnimationFrame(function tick(now) {
      const prev = reveal.current;
      reveal.current = advance(prev, Math.max(0, now - last));
      last = now;
      const caughtUp = reveal.current.pos >= reveal.current.text.length;
      if (reveal.current !== prev && (caughtUp || visibleText(reveal.current) !== visibleText(prev))) {
        rerender((n) => n + 1);
      }
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [behind, reduceMotion]);

  return reduceMotion ? text : visibleText(reveal.current);
}
