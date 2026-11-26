import { useEffect, useLayoutEffect, useState } from 'react';
import { typingSpeed } from './typing';

const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;

/** Width of the soft fade at the typing edge, in px. */
const EDGE_PX = 28;
/** Space kept between the line being typed and the bottom of the chat while following it. */
const FOLLOW_MARGIN_PX = 28;
/** Share of the remaining distance the follow-scroll covers each frame (eases the motion). */
const FOLLOW_EASE = 0.22;

/** The text nodes of `root` in reading order, with their combined length. */
function textNodes(root: HTMLElement): { nodes: Text[]; total: number } {
  const nodes: Text[] = [];
  let total = 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = n as Text;
    if (!text.data.length) continue;
    nodes.push(text);
    total += text.data.length;
  }
  return { nodes, total };
}

/**
 * Where the `index`-th character sits inside `root`: its line's top and bottom and the
 * x position just past it, all relative to `root`. Null when it has no box (hidden text).
 */
function caretBox(root: HTMLElement, nodes: Text[], index: number): { top: number; bottom: number; x: number } | null {
  let remaining = index;
  for (const node of nodes) {
    if (remaining < node.data.length) {
      const range = document.createRange();
      range.setStart(node, remaining);
      range.setEnd(node, remaining + 1);
      const rects = range.getClientRects();
      const rect = rects[rects.length - 1];
      if (!rect || (rect.width === 0 && rect.height === 0)) return null;
      const box = root.getBoundingClientRect();
      return { top: rect.top - box.top, bottom: rect.bottom - box.top, x: rect.right - box.left };
    }
    remaining -= node.data.length;
  }
  return null;
}

const MASK_PROPS = ['maskImage', 'maskSize', 'maskPosition', 'maskRepeat'] as const;

function setMask(el: HTMLElement, values: Record<(typeof MASK_PROPS)[number], string> | null) {
  const style = el.style as unknown as Record<string, string>;
  for (const prop of MASK_PROPS) {
    const value = values ? values[prop] : '';
    style[prop] = value;
    style[`webkit${prop[0].toUpperCase()}${prop.slice(1)}`] = value;
  }
}

/**
 * Types a reply out. The reply is laid out whole from the start (so nothing reflows or
 * changes formatting while it types) and a soft-edged mask sweeps over it line by line,
 * following where each character actually sits. The same loop keeps the line being typed
 * in view, until the reader scrolls up on their own.
 *
 * Decided once, when the row mounts: history, streamed replies and reduced motion show
 * whole. Returns whether typing is running and whether this row was typed at all.
 */
export function useTypingReveal(
  rootRef: React.RefObject<HTMLElement>,
  enabled: boolean,
): { typing: boolean; typed: boolean } {
  const [typed] = useState(() => enabled && !reducedMotion());
  const [typing, setTyping] = useState(typed);

  // Hide the text before the first paint so a typed reply never flashes whole.
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!typing || !root) return;
    setMask(root, { maskImage: 'linear-gradient(transparent, transparent)', maskSize: '100% 100%', maskPosition: '0 0', maskRepeat: 'no-repeat' });
  }, [rootRef, typing]);

  useEffect(() => {
    const root = rootRef.current;
    if (!typing || !root) return;
    const scroller = root.closest<HTMLElement>('.gas-scroll');

    // Follow the typing until the reader scrolls up themselves.
    let follow = true;
    let lastSetTop = scroller ? scroller.scrollTop : 0;
    const onScroll = () => {
      if (scroller && scroller.scrollTop < lastSetTop - 2) follow = false;
      if (scroller) lastSetTop = Math.max(lastSetTop, scroller.scrollTop);
    };
    scroller?.addEventListener('scroll', onScroll, { passive: true });

    let shown = 0;
    let last = performance.now();
    const finish = () => {
      setMask(root, null);
      setTyping(false);
      // Still following: bring the whole reply into view, including what appears with it
      // once typing ends (its suggestions and thumbs), after they have rendered.
      if (follow && scroller) {
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            const row = root.closest<HTMLElement>('.gas-row') ?? root;
            const rowBottom =
              row.getBoundingClientRect().bottom - scroller.getBoundingClientRect().top + scroller.scrollTop;
            const target = rowBottom + FOLLOW_MARGIN_PX - scroller.clientHeight;
            if (target > scroller.scrollTop) scroller.scrollTo({ top: target, behavior: 'smooth' });
          }),
        );
      }
    };
    let frame = requestAnimationFrame(function tick(now) {
      try {
        step(now);
      } catch {
        // Never leave a reply hidden: on any error, show it whole.
        finish();
      }
    });
    function step(now: number) {
      const { nodes, total } = textNodes(root!);
      // rAF's timestamp can be a little older than the start time; never step backwards,
      // and a background tab must not jump ahead.
      const elapsed = Math.max(0, Math.min(64, now - last));
      last = now;
      if (total > 0) shown = Math.min(total, shown + (typingSpeed(total) * elapsed) / 1000);

      if (total > 0 && shown >= total) {
        finish();
        return;
      }

      const box = total > 0 ? caretBox(root!, nodes, Math.min(total - 1, Math.max(0, Math.floor(shown)))) : null;
      if (box) {
        const lineHeight = Math.max(1, box.bottom - box.top);
        setMask(root!, {
          maskImage: `linear-gradient(#000, #000), linear-gradient(to right, #000 ${box.x - EDGE_PX}px, transparent ${box.x}px)`,
          maskSize: `100% ${Math.max(0, box.top)}px, 100% ${lineHeight}px`,
          maskPosition: `0 0, 0 ${box.top}px`,
          maskRepeat: 'no-repeat',
        });

        if (follow && scroller) {
          const lineBottom =
            root!.getBoundingClientRect().top + box.bottom - scroller.getBoundingClientRect().top + scroller.scrollTop;
          const target = lineBottom + FOLLOW_MARGIN_PX - scroller.clientHeight;
          if (target > scroller.scrollTop + 0.5) {
            const next = scroller.scrollTop + Math.max(1, (target - scroller.scrollTop) * FOLLOW_EASE);
            lastSetTop = next;
            scroller.scrollTop = next;
          }
        }
      }
      frame = requestAnimationFrame((t) => {
        try {
          step(t);
        } catch {
          finish();
        }
      });
    }

    return () => {
      cancelAnimationFrame(frame);
      scroller?.removeEventListener('scroll', onScroll);
      setMask(root, null);
    };
  }, [rootRef, typing]);

  return { typing, typed };
}
