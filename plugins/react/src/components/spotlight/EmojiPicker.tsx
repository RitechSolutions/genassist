import React, { useEffect, useRef, useState } from 'react';
import { Smile } from 'lucide-react';
import type { SpotlightController } from './types';

/** The quick set offered in the picker (two rows of eight). */
export const SPOTLIGHT_EMOJIS = [
  '🙂', '😁', '😂', '😊', '😍', '😐', '😕', '😒',
  '😢', '😭', '🎉', '❤️', '👌', '👍', '👎', '🙏',
];
const COLUMNS = 8;

/** `text` with `insert` put in place of the [start, end) selection, and the caret after it. */
export function insertAtSelection(text: string, insert: string, start: number, end: number): { value: string; caret: number } {
  const from = Math.max(0, Math.min(start, text.length));
  const to = Math.max(from, Math.min(end, text.length));
  return { value: text.slice(0, from) + insert + text.slice(to), caret: from + insert.length };
}

/**
 * The composer's emoji button and its picker. The picker opens above the composer (it is
 * positioned against the composer form). Picking an emoji inserts it at the caret, closes
 * the picker and puts focus back in the message field; outside click or Escape closes it.
 */
export const EmojiPicker: React.FC<{ ctl: SpotlightController; disabled: boolean }> = ({ ctl, disabled }) => {
  const { t } = ctl;
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const label = t('spotlight.emoji', 'Add emoji');

  const close = (refocus: boolean) => {
    setOpen(false);
    if (refocus) buttonRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      const target = e.target as Node;
      if (!panelRef.current?.contains(target) && !buttonRef.current?.contains(target)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        close(true);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
      document.removeEventListener('keydown', onKey, true);
    };
  }, [open]);

  // A disabled composer (finalized, pending form) closes the picker too.
  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  const insert = (emoji: string) => {
    const el = ctl.textAreaRef.current;
    const current = ctl.inputValue;
    const start = el ? el.selectionStart : current.length;
    const end = el ? el.selectionEnd : current.length;
    const { value, caret } = insertAtSelection(current, emoji, start, end);
    ctl.setInputValue(value);
    // One pick closes the picker and hands focus back to the message field, caret after
    // the emoji, so the visitor can press Enter (or send) right away.
    setOpen(false);
    requestAnimationFrame(() => {
      const ta = ctl.textAreaRef.current;
      if (!ta) return;
      ta.focus();
      ta.setSelectionRange(caret, caret);
    });
  };

  // Arrow keys move through the 8-column grid.
  const onGridKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(panelRef.current?.querySelectorAll<HTMLButtonElement>('button') ?? []);
    const index = items.indexOf(document.activeElement as HTMLButtonElement);
    if (index === -1) return;
    const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: COLUMNS, ArrowUp: -COLUMNS }[e.key];
    if (step === undefined) return;
    e.preventDefault();
    items[Math.max(0, Math.min(items.length - 1, index + step))]?.focus();
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className="gas-icon-btn gas-emoji-btn"
        disabled={disabled}
        aria-label={label}
        title={label}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => (open ? close(false) : setOpen(true))}
      >
        <Smile size={19} />
      </button>
      {open && (
        <div ref={panelRef} className="gas-emoji-panel" role="dialog" aria-label={label} onKeyDown={onGridKey}>
          {SPOTLIGHT_EMOJIS.map((emoji) => (
            <button key={emoji} type="button" className="gas-emoji" aria-label={emoji} onClick={() => insert(emoji)}>
              {emoji}
            </button>
          ))}
        </div>
      )}
    </>
  );
};
