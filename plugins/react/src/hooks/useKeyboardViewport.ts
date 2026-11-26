import { useEffect, useState } from 'react';

/**
 * Where the on-screen keyboard leaves room for the chat.
 *
 * Mobile browsers open the keyboard over the page instead of shrinking it (iOS Safari
 * always; Chrome on Android by default): fixed elements stay where they were, behind the
 * keyboard, and the browser pans the whole page to bring the field into view. The visual
 * viewport API reports the part still visible, so the chat can fit itself into it.
 */
export interface KeyboardViewport {
  /** The keyboard is up over one of the chat's own fields. */
  open: boolean;
  /** Top of the visible area, from the top of the layout viewport (px). */
  top: number;
  /** Height of the visible area (px). */
  height: number;
  /** How much of the layout viewport's bottom the keyboard covers (px). */
  inset: number;
}

export const KEYBOARD_CLOSED: KeyboardViewport = { open: false, top: 0, height: 0, inset: 0 };

/** Less than this between the layout and visible heights is browser chrome (toolbars), not a keyboard. */
export const KEYBOARD_MIN_HEIGHT = 120;

export interface ViewportSample {
  /** Height of the layout viewport, the box fixed elements are positioned in. */
  layoutHeight: number;
  visualHeight: number;
  visualTop: number;
  /** Pinch zoom (1 = none). */
  scale: number;
  /** A text field inside the chat has focus. */
  chatFieldFocused: boolean;
}

/** The keyboard state for one reading of the viewport. */
export function keyboardViewport(s: ViewportSample): KeyboardViewport {
  // Zoomed in, the visible area is small for another reason: leave the layout alone.
  if (!s.chatFieldFocused || s.scale > 1.01) return KEYBOARD_CLOSED;
  const covered = s.layoutHeight - s.visualHeight;
  if (!(covered >= KEYBOARD_MIN_HEIGHT) || s.visualHeight <= 0) return KEYBOARD_CLOSED;
  const top = Math.max(0, Math.round(s.visualTop));
  const height = Math.round(s.visualHeight);
  return { open: true, top, height, inset: Math.max(0, Math.round(s.layoutHeight - s.visualHeight - s.visualTop)) };
}

export const sameKeyboardViewport = (a: KeyboardViewport, b: KeyboardViewport): boolean =>
  a.open === b.open && a.top === b.top && a.height === b.height && a.inset === b.inset;

const CHAT_SELECTOR = '[data-genassist-root], [data-genassist-container], [data-genassist-field]';

function isTextField(el: Element): boolean {
  if (el instanceof HTMLTextAreaElement) return true;
  if (el instanceof HTMLInputElement) {
    return !['checkbox', 'radio', 'button', 'submit', 'reset', 'file', 'range', 'color', 'image', 'hidden'].includes(el.type);
  }
  return el instanceof HTMLElement && el.isContentEditable;
}

/** The focused element, looking inside shadow roots (the widget may be mounted in one). */
function focusedElement(): Element | null {
  let el: Element | null = document.activeElement;
  while (el && el.shadowRoot && el.shadowRoot.activeElement) el = el.shadowRoot.activeElement;
  return el;
}

/** A text field of the chat has focus (not one of the host page's own fields). */
export function chatFieldFocused(): boolean {
  const el = focusedElement();
  return Boolean(el && isTextField(el) && el.closest(CHAT_SELECTOR));
}

function layoutHeight(): number {
  // documentElement.clientHeight is the layout viewport in standards mode; innerHeight can
  // follow the visual viewport in some browsers, so take the larger of the two.
  const client = document.compatMode === 'CSS1Compat' ? document.documentElement.clientHeight : 0;
  return Math.max(window.innerHeight || 0, client || 0);
}

function sample(): KeyboardViewport {
  const vv = window.visualViewport;
  if (!vv) return KEYBOARD_CLOSED;
  return keyboardViewport({
    layoutHeight: layoutHeight(),
    visualHeight: vv.height,
    visualTop: vv.offsetTop,
    scale: vv.scale || 1,
    chatFieldFocused: chatFieldFocused(),
  });
}

/** Follows the on-screen keyboard while a chat field has focus; KEYBOARD_CLOSED otherwise. */
export function useKeyboardViewport(enabled: boolean = true): KeyboardViewport {
  const [state, setState] = useState<KeyboardViewport>(KEYBOARD_CLOSED);

  useEffect(() => {
    if (!enabled || typeof window === 'undefined' || !window.visualViewport) {
      setState(KEYBOARD_CLOSED);
      return;
    }
    const vv = window.visualViewport;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const next = sample();
        setState((prev) => (sameKeyboardViewport(prev, next) ? prev : next));
      });
    };
    // focusout fires before the next field takes focus: wait a frame (update does) so
    // moving between the chat's own fields doesn't flicker the layout.
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    window.addEventListener('resize', update);
    document.addEventListener('focusin', update);
    document.addEventListener('focusout', update);
    update();
    return () => {
      cancelAnimationFrame(frame);
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
      document.removeEventListener('focusin', update);
      document.removeEventListener('focusout', update);
    };
  }, [enabled]);

  return state;
}
