import { useLayoutEffect, useRef } from "react";
import type { KeyboardEvent } from "react";

export const COMPOSER_MAX_HEIGHT = 240;

// Grows a controlled textarea to fit its content, up to maxHeight, then scrolls.
// Driven by `value`, so it also shrinks back on its own once a message is sent.
export function useAutoGrowTextarea(
  value: string,
  maxHeight: number = COMPOSER_MAX_HEIGHT
) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    // scrollHeight excludes the border, but box-sizing is border-box, so the
    // border has to be added back or every bordered composer clips its last line.
    const border = el.offsetHeight - el.clientHeight;
    const wanted = el.scrollHeight + border;
    el.style.height = `${Math.min(wanted, maxHeight)}px`;
    el.style.overflowY = wanted > maxHeight ? "auto" : "hidden";
  }, [value, maxHeight]);

  return ref;
}

// The composer convention: Enter sends, Shift+Enter inserts a newline.
export function submitOnEnter(onSubmit: () => void) {
  return (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // isComposing is true for the Enter that commits an IME candidate (CJK),
    // which must not send the half-typed message.
    if (event.key !== "Enter" || event.shiftKey) return;
    if (event.nativeEvent.isComposing) return;
    event.preventDefault();
    onSubmit();
  };
}
