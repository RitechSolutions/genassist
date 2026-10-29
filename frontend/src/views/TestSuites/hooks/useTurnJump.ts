import { useEffect, useRef, useState } from "react";

// How long a turn stays marked after a link brought it into view.
const MARKED_MS = 1600;

/** Brings a turn into view and marks it for a moment, so the eye lands on it. */
export const useTurnJump = () => {
  const refs = useRef(new Map<string, HTMLElement>());
  const [marked, setMarked] = useState<string | null>(null);
  useEffect(() => {
    if (!marked) return;
    const timer = window.setTimeout(() => setMarked(null), MARKED_MS);
    return () => window.clearTimeout(timer);
  }, [marked]);
  const jump = (key: string) => {
    refs.current.get(key)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setMarked(key);
  };
  const ref = (key: string) => (element: HTMLElement | null) => {
    if (element) refs.current.set(key, element);
    else refs.current.delete(key);
  };
  return { jump, ref, marked };
};

// A ring set off from the turn, so marking it moves nothing.
export const MARK = "rounded-lg transition-shadow duration-500";
export const MARKED = "ring-2 ring-primary/50 ring-offset-8 ring-offset-card";
