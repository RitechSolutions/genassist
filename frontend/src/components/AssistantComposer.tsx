import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Sparkles } from "lucide-react";

import { cn } from "@/helpers/utils";
import { tokenizeComposerText } from "@/components/assistantComposerTokens";

// The field grows with its content up to this height, then scrolls.
const MAX_FIELD_HEIGHT_PX = 200;
// The hero box starts tall enough to invite a few sentences.
const HERO_MIN_HEIGHT_PX = 72;
// Shared by the textarea and its highlight layer: they must lay out text identically.
const FIELD_TEXT_CLASSES = "py-1.5 text-sm leading-5 break-words";
const HERO_TEXT_CLASSES = "py-1 text-[15px] leading-6 break-words";

export interface ComposerMentionable {
  id: string;
  name: string;
  /** Small secondary text in the picker (a node type, a role). */
  hint?: string;
  /** Shown in front of the name in the picker (a step's icon tile). */
  icon?: React.ReactNode;
}

export interface ComposerCommand {
  name: string;
  description: string;
}

type AssistantComposerProps = {
  value: string;
  onChange: (value: string) => void;
  /** Receives the trimmed message; the composer clears the field itself. */
  onSubmit: (message: string) => void;
  placeholder?: string;
  /** Blocks typing and sending while the assistant is answering. */
  busy?: boolean;
  className?: string;
  /** Things the person can @-mention (typing "@" opens a picker). */
  mentionables?: ComposerMentionable[];
  /** Commands offered when the message starts with "/". */
  commands?: ComposerCommand[];
  /**
   * Called when a mention is picked from the picker. The mention stays in the field
   * as "@Name" (shown as a badge); the caller may mirror it elsewhere.
   */
  onMentionPick?: (mention: ComposerMentionable) => void | boolean;
  /**
   * Controls shown in a row under the text (a toggle, a context chip). With a toolbar,
   * or in the hero size, the send button sits in that row rather than beside the text.
   */
  toolbar?: React.ReactNode;
  /** "hero": the large, centred opening box; "inline": the one-line field that grows. */
  size?: "inline" | "hero";
  /** Starting height of the text field in pixels; defaults to the size's own (72 for hero, one line inline). */
  minHeightPx?: number;
  /** Leave out the sparkle in front of the one-line field. */
  noIcon?: boolean;
  /** Shown inside the box above the text (the steps a message is about). */
  header?: React.ReactNode;
  autoFocus?: boolean;
  /** Fired on Escape with an empty field (closing a dialog). */
  onEscape?: () => void;
  /** Hard cap on the message length; a counter appears as the text nears it. */
  maxLength?: number;
};

interface Picker {
  kind: "mention" | "command";
  /** Index in `value` where the "@" or "/" sits. */
  start: number;
  query: string;
}

/**
 * The message box for the assistant surfaces: one rounded field with the send control inside it.
 * It starts as a single line and grows as the message wraps or gains lines (Shift+Enter).
 * Shared by the workflow builder's Conversational tab and the conversation detail's Ask GenAI
 * pane so both compose messages the same way.
 *
 * With `mentionables`, typing "@" opens a picker and the chosen name is inserted as "@Name";
 * with `commands`, a message starting with "/" offers the commands. Both are drawn as
 * badges inside the field: a highlight layer behind the (transparent) textarea renders
 * the same text with the tokens tinted, so typing, selection and the caret stay native.
 */
export function AssistantComposer({
  value,
  onChange,
  onSubmit,
  placeholder = "Ask GenAI...",
  busy = false,
  className,
  mentionables,
  commands,
  onMentionPick,
  toolbar,
  size = "inline",
  minHeightPx,
  noIcon = false,
  header,
  autoFocus = false,
  onEscape,
  maxLength,
}: AssistantComposerProps) {
  const canSend = value.trim().length > 0 && !busy;
  // Shown only near the cap, so a silently truncated paste is never a mystery.
  const nearLimit = maxLength !== undefined && value.length >= maxLength * 0.9;
  const counter =
    maxLength !== undefined && nearLimit ? (
      <span
        aria-live="polite"
        className={cn(
          "shrink-0 text-[11px] tabular-nums",
          value.length >= maxLength ? "text-destructive" : "text-muted-foreground"
        )}
      >
        {value.length.toLocaleString()} / {maxLength.toLocaleString()}
      </span>
    ) : null;
  const hero = size === "hero";
  const twoRows = hero || Boolean(toolbar) || Boolean(header);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const decorated = Boolean(mentionables?.length || commands?.length);
  const tokens = useMemo(
    () => (decorated ? tokenizeComposerText(value, mentionables, commands) : []),
    [decorated, value, mentionables, commands]
  );
  const hasBadges = tokens.some((token) => token.kind !== "text");
  // The highlight layer must scroll with the field once the text overflows.
  const syncScroll = useCallback(() => {
    const field = fieldRef.current;
    const highlight = highlightRef.current;
    if (field && highlight) highlight.scrollTop = field.scrollTop;
  }, []);
  const [picker, setPicker] = useState<Picker | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const fitToContent = useCallback(() => {
    const field = fieldRef.current;
    if (!field) return;
    field.style.height = "auto";
    const minHeight = minHeightPx ?? (hero ? HERO_MIN_HEIGHT_PX : 0);
    const contentHeight = Math.max(field.scrollHeight, minHeight);
    field.style.height = `${Math.min(contentHeight, MAX_FIELD_HEIGHT_PX)}px`;
    field.style.overflowY = contentHeight > MAX_FIELD_HEIGHT_PX ? "auto" : "hidden";
  }, [hero, minHeightPx]);

  useLayoutEffect(fitToContent, [value, fitToContent]);

  useEffect(() => {
    if (autoFocus) fieldRef.current?.focus();
  }, [autoFocus]);

  // The text re-wraps when the surrounding panel is resized, so refit on width changes.
  useEffect(() => {
    const field = fieldRef.current;
    if (!field || typeof ResizeObserver === "undefined") return;
    let lastWidth = field.clientWidth;
    const observer = new ResizeObserver(() => {
      if (field.clientWidth === lastWidth) return;
      lastWidth = field.clientWidth;
      fitToContent();
    });
    observer.observe(field);
    return () => observer.disconnect();
  }, [fitToContent]);

  // Work out whether the caret sits in an "@query" or a leading "/query".
  const detectPicker = useCallback(
    (text: string, caret: number): Picker | null => {
      const before = text.slice(0, caret);
      if (commands?.length) {
        const command = /^\/([a-z]*)$/i.exec(before);
        if (command) return { kind: "command", start: 0, query: command[1] };
      }
      if (mentionables?.length) {
        const mention = /(?:^|\s)@([^@\n]*)$/.exec(before);
        if (mention) {
          return { kind: "mention", start: caret - mention[1].length - 1, query: mention[1] };
        }
      }
      return null;
    },
    [commands, mentionables]
  );

  const options = useMemo(() => {
    if (!picker) return [];
    const query = picker.query.toLowerCase();
    if (picker.kind === "command") {
      return (commands ?? [])
        .filter((c) => c.name.startsWith(query))
        .map((c) => ({ key: c.name, label: `/${c.name}`, hint: c.description, icon: undefined as React.ReactNode }));
    }
    return (mentionables ?? [])
      .filter((m) => m.name.toLowerCase().includes(query))
      .slice(0, 8)
      .map((m) => ({ key: m.id, label: m.name, hint: m.hint, icon: m.icon }));
  }, [picker, commands, mentionables]);

  useEffect(() => setActiveIndex(0), [options.length, picker?.query]);

  const choose = (option: { key: string; label: string }) => {
    if (!picker) return;
    const field = fieldRef.current;
    const caret = field?.selectionStart ?? value.length;
    const insert = picker.kind === "command" ? `${option.label} ` : `@${option.label} `;
    if (picker.kind === "mention" && onMentionPick) {
      const mention = mentionables?.find((m) => m.id === option.key);
      if (mention) onMentionPick(mention);
    }
    const next = value.slice(0, picker.start) + insert + value.slice(caret);
    onChange(next);
    setPicker(null);
    requestAnimationFrame(() => {
      const position = picker.start + insert.length;
      field?.focus();
      field?.setSelectionRange(position, position);
    });
  };

  const submit = () => {
    if (!canSend) return;
    setPicker(null);
    onSubmit(value.trim());
    onChange("");
  };

  return (
    <div className={cn("relative", className)}>
      {picker && options.length > 0 && (
        <ul
          role="listbox"
          className="absolute bottom-full left-0 right-0 z-30 mb-2 max-h-56 overflow-y-auto rounded-xl border border-border bg-popover p-1 shadow-lg"
        >
          {options.map((option, index) => (
            <li key={option.key}>
              <button
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                onMouseDown={(event) => {
                  event.preventDefault();
                  choose(option);
                }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm",
                  index === activeIndex ? "bg-accent text-accent-foreground" : "hover:bg-muted"
                )}
              >
                {option.icon}
                <span className="font-medium">{option.label}</span>
                {option.hint && (
                  <span className="truncate text-xs text-muted-foreground">{option.hint}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div
        className={cn(
          "border border-border bg-white shadow-sm transition-all dark:bg-zinc-900",
          twoRows
            ? cn("flex flex-col gap-1", hero ? "rounded-[22px] px-4 pb-2.5 pt-3.5" : "rounded-2xl px-3 pb-1.5 pt-2")
            : "flex items-end gap-2 rounded-3xl py-1.5 pl-3.5 pr-1.5",
          busy && "opacity-60"
        )}
        onClick={(event) => {
          if (event.target === event.currentTarget) fieldRef.current?.focus();
        }}
      >
        {header && <div className="mb-1 flex flex-wrap items-center gap-1">{header}</div>}
        {!twoRows && !noIcon && (
          <Sparkles
            className="pointer-events-none mb-2 h-4 w-4 shrink-0 text-[hsl(var(--brand-600))]"
            aria-hidden
          />
        )}
        <div className="relative min-w-0 flex-1">
        {hasBadges && (
          <div
            ref={highlightRef}
            aria-hidden
            className={cn(hero ? HERO_TEXT_CLASSES : FIELD_TEXT_CLASSES, "pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words text-foreground")}
          >
            {tokens.map((token, index) =>
              token.kind === "text" ? (
                <span key={index}>{token.text}</span>
              ) : (
                <span
                  key={index}
                  className={cn(
                    "rounded-md [box-decoration-break:clone] [-webkit-box-decoration-break:clone]",
                    token.kind === "command"
                      ? "bg-amber-500/15 text-amber-700 shadow-[0_0_0_2px_rgb(245_158_11/0.15)] dark:text-amber-400"
                      : "bg-[hsl(var(--brand-600))]/15 text-[hsl(var(--brand-600))] shadow-[0_0_0_2px_hsl(var(--brand-600)/0.15)]"
                  )}
                >
                  {token.kind === "mention" ? (
                    <>
                      <span className="opacity-50">@</span>
                      {token.text.slice(1)}
                    </>
                  ) : (
                    token.text
                  )}
                </span>
              )
            )}
            {/* A trailing newline needs a character after it to keep the last line's height. */}
            {value.endsWith("\n") ? "\u200b" : null}
          </div>
        )}
        <textarea
          ref={fieldRef}
          rows={1}
          value={value}
          onScroll={syncScroll}
          onChange={(event) => {
            onChange(event.target.value);
            setPicker(detectPicker(event.target.value, event.target.selectionStart ?? event.target.value.length));
          }}
          onKeyDown={(event) => {
            if (picker && options.length > 0) {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActiveIndex((i) => (i + 1) % options.length);
                return;
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setActiveIndex((i) => (i - 1 + options.length) % options.length);
                return;
              }
              if (event.key === "Enter" || event.key === "Tab") {
                event.preventDefault();
                choose(options[activeIndex]);
                return;
              }
              if (event.key === "Escape") {
                setPicker(null);
                return;
              }
            }
            if (event.key === "Escape" && !value.trim() && onEscape) {
              event.preventDefault();
              onEscape();
              return;
            }
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
          onBlur={() => setPicker(null)}
          placeholder={placeholder}
          maxLength={maxLength}
          disabled={busy}
          aria-label={placeholder}
          className={cn(
            hero ? HERO_TEXT_CLASSES : FIELD_TEXT_CLASSES,
            "relative block w-full resize-none bg-transparent placeholder:text-muted-foreground focus:outline-none disabled:cursor-not-allowed",
            hasBadges && "text-transparent caret-foreground"
          )}
        />
        </div>
        {twoRows ? (
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 flex-1 items-center gap-1.5">{toolbar}</div>
            {counter}
            <SendButton onClick={submit} disabled={!canSend} />
          </div>
        ) : (
          <>
            {counter && <span className="mb-2 flex shrink-0 items-center">{counter}</span>}
            <SendButton onClick={submit} disabled={!canSend} />
          </>
        )}
      </div>
    </div>
  );
}

const SendButton: React.FC<{ onClick: () => void; disabled: boolean }> = ({ onClick, disabled }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    aria-label="Send message"
    // The GenAssist logo blue, dimmed (not greyed) while there is nothing to send.
    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#204BFF] text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-[#204BFF]/30 disabled:text-white/70 disabled:opacity-100"
  >
    <ArrowUp className="h-4 w-4" aria-hidden />
  </button>
);
