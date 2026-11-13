import React, { useEffect, useRef, useState, useMemo } from "react";
import {
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Copy,
  FlaskConical,
  Globe,
  Lightbulb,
  Loader2,
  PencilLine,
  Plus,
  Pencil,
  ShieldCheck,
  Sparkles,
  Square,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Volume2,
} from "lucide-react";

import { cn } from "@/helpers/utils";
import type { BuilderChange } from "@/services/workflowBuilder";
import {
  changeKind,
  describeWork,
  type AssistantStep,
  type LiveTurn,
  isThoughtText,
  stripThoughtMarker,
} from "@/views/AIAgents/Workflows/utils/assistantDraft";

const CHANGE_BADGE = {
  add: "bg-green-50 text-green-700 border-green-200 dark:bg-green-500/15 dark:text-green-400 dark:border-green-500/30",
  update: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/15 dark:text-blue-400 dark:border-blue-500/30",
  remove: "bg-red-50 text-red-700 border-red-200 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30",
};

/**
 * Motion for the assistant chat: the reasoning trail while a reply is on its
 * way (what the assistant is doing, in its own words, as it happens), the
 * collapsed trail kept under a finished reply, and a typewriter reveal for a
 * reply that arrived whole. All respect the reduced-motion preference.
 */

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const STEP_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  read: BookOpen,
  lookup: BookOpen,
  search: Globe,
  edit: PencilLine,
  test: FlaskConical,
  finalize: ShieldCheck,
  question: CircleHelp,
  thought: Lightbulb,
};

const useElapsed = (since: number, running: boolean) => {
  const [elapsed, setElapsed] = useState(() => Date.now() - since);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setElapsed(Date.now() - since), 1000);
    return () => clearInterval(timer);
  }, [since, running]);
  return elapsed;
};

const formatSeconds = (ms: number) => {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m ${seconds % 60}s` : `${seconds}s`;
};

const StepRow: React.FC<{ step: AssistantStep; live: boolean }> = ({ step, live }) => {
  const Icon = STEP_ICONS[step.kind] ?? Sparkles;
  const running = live && !step.done;
  if (step.kind === "thought") {
    return (
      <li className="ai-step-in flex gap-2.5">
        <span className="mt-[3px] flex h-4 w-4 shrink-0 items-center justify-center text-amber-500">
          <Lightbulb className="h-3.5 w-3.5" />
        </span>
        <p className="min-w-0 whitespace-pre-wrap text-[13px] leading-5 text-muted-foreground">
          {step.text}
          {running && <span className="ai-caret" aria-hidden />}
        </p>
      </li>
    );
  }
  return (
    <li className="ai-step-in flex items-start gap-2.5">
      <span
        className={cn(
          "mt-[3px] flex h-4 w-4 shrink-0 items-center justify-center",
          running ? "text-[hsl(var(--brand-600))]" : "text-muted-foreground"
        )}
      >
        {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      </span>
      <span className="min-w-0 text-[13px] leading-5">
        <span className={cn(running ? "ai-shimmer-text" : "text-foreground")}>{step.text}</span>
        {step.detail && (
          <span
            className={cn(
              "ml-1.5 inline-flex items-center gap-1 text-xs",
              /fail|reject|stopped|not /i.test(step.detail) ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"
            )}
          >
            {!/fail|reject|stopped|not /i.test(step.detail) && <Check className="h-3 w-3" />}
            {step.detail}
          </span>
        )}
      </span>
    </li>
  );
};

// Order in which the nine tiles light: around the ring, then the centre.
const CUBE_ORDER = [0, 1, 2, 7, 8, 3, 6, 5, 4];

/**
 * Nine tiny tiles, the same rounded squares as the hover grid, lighting up in
 * sequence around a ring with the centre pulsing: the "working" mark in front
 * of "Thinking". Pure CSS; still under reduced motion.
 */
export const ThinkingCubes: React.FC<{ className?: string }> = ({ className }) => (
  <span className={cn("ai-cubes", className)} aria-hidden>
    {CUBE_ORDER.map((order, index) => (
      <span key={index} style={{ "--i": order } as React.CSSProperties} />
    ))}
  </span>
);

/** About four rows tall; the rest scrolls (no visible bar) and follows the newest row. */
const LIVE_TRAIL_MAX_HEIGHT = "6.75rem";
const NO_STEPS: AssistantStep[] = [];

/**
 * The turn in progress: "Thinking · 3s" with a disclosure that lists what the
 * assistant is doing as it happens. The list is about four rows tall and keeps
 * every row: it scrolls without a visible bar and follows the newest row unless
 * the person has scrolled up to read earlier ones. Text streaming in
 * that carries the thought marker shows as a thought row from its first token
 * and becomes a committed thought when the call starts, with no visual jump;
 * any other text is the reply and streams below as a normal message.
 */
export const ReasoningTrail: React.FC<{ turn: LiveTurn | null }> = ({ turn }) => {
  const startedAt = turn?.startedAt ?? Date.now();
  const elapsed = useElapsed(startedAt, true);
  const steps = turn?.steps ?? NO_STEPS;
  const text = turn?.text ?? "";
  const [open, setOpen] = useState(true);
  const listRef = useRef<HTMLUListElement>(null);
  const liveThought = isThoughtText(text) ? stripThoughtMarker(text) : "";
  const rows = useMemo<AssistantStep[]>(
    () => (liveThought ? [...steps, { id: "live-thought", kind: "thought", text: liveThought, done: false }] : steps),
    [steps, liveThought]
  );
  const hasRows = rows.length > 0;
  // Follow the newest row, but not while the person is reading further up.
  const pinnedToEnd = useRef(true);
  const onScroll = () => {
    const el = listRef.current;
    if (el) pinnedToEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < 8;
  };
  useEffect(() => {
    const el = listRef.current;
    if (el && pinnedToEnd.current) el.scrollTop = el.scrollHeight;
  }, [rows.length, text.length, open]);

  return (
    <div className="space-y-2" role="status" aria-live="polite">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        disabled={!hasRows}
        className="inline-flex items-center gap-2 text-[13px] text-muted-foreground transition-colors hover:text-foreground disabled:cursor-default"
      >
        <ThinkingCubes />
        <span className="ai-shimmer-text">Thinking</span>
        <span>· {formatSeconds(elapsed)}</span>
        {hasRows && (open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />)}
      </button>
      {open && hasRows && (
        <ul
          ref={listRef}
          onScroll={onScroll}
          style={{ maxHeight: LIVE_TRAIL_MAX_HEIGHT }}
          className="ai-no-scrollbar ml-1 space-y-1.5 overflow-y-auto border-l-2 border-border/70 py-0.5 pl-3 pr-1"
        >
          {rows.map((step) => (
            <StepRow key={step.id} step={step} live />
          ))}
        </ul>
      )}
      {!liveThought && text.trim() && (
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
          {text}
          <span className="ai-caret" aria-hidden />
        </div>
      )}
    </div>
  );
};

/**
 * Above a finished reply: "Finished thinking" with a disclosure that unfolds the
 * steps the assistant took, its thoughts, and what it changed on the canvas.
 */
export const WorkSummary: React.FC<{ steps?: AssistantStep[]; workedMs?: number; changes?: BuilderChange[] }> = ({
  steps,
  workedMs,
  changes,
}) => {
  const [open, setOpen] = useState(false);
  const summary = describeWork(steps, workedMs, changes);
  if (!summary) return null;
  return (
    <div className="mb-1.5">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        title={summary}
        className="inline-flex items-center gap-1.5 py-0.5 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
      >
        Finished thinking
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
      </button>
      {open && (
        <div className="ml-1 mt-1 space-y-2 border-l-2 border-border/70 py-0.5 pl-3">
          {steps && steps.length > 0 && (
            <ul className="space-y-1.5">
              {steps.map((step) => (
                <StepRow key={step.id} step={step} live={false} />
              ))}
            </ul>
          )}
          {changes && changes.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {changes.map((change, index) => {
                const kind = changeKind(change);
                const Icon = kind === "add" ? Plus : kind === "update" ? Pencil : Trash2;
                return (
                  <span
                    key={`${change.op}-${index}`}
                    className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs ${CHANGE_BADGE[kind]}`}
                  >
                    <Icon className="h-3 w-3" />
                    {change.summary}
                  </span>
                );
              })}
            </div>
          )}
          <p className="text-[11px] text-muted-foreground">{summary}</p>
        </div>
      )}
    </div>
  );
};

/** Under a reply: copy it, hear it read aloud, and say whether it was helpful. */
export const MessageActions: React.FC<{
  text: string;
  reaction?: "up" | "down";
  onReact?: (reaction: "up" | "down" | null) => void;
}> = ({ text, reaction, onReact }) => {
  const [copied, setCopied] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be refused; nothing to do.
    }
  };
  const speak = () => {
    if (!canSpeak) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  };
  useEffect(() => () => {
    if (speaking && canSpeak) window.speechSynthesis.cancel();
  }, [speaking, canSpeak]);

  const button = "inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground";
  return (
    <div className="mt-2 flex items-center gap-0.5">
      <button type="button" onClick={copy} className={button} title={copied ? "Copied" : "Copy"} aria-label="Copy reply">
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
      {canSpeak && (
        <button type="button" onClick={speak} className={cn(button, speaking && "text-foreground")} title={speaking ? "Stop" : "Read aloud"} aria-label={speaking ? "Stop reading" : "Read aloud"}>
          {speaking ? <Square className="h-3 w-3" /> : <Volume2 className="h-3.5 w-3.5" />}
        </button>
      )}
      {onReact && (
        <>
          <button
            type="button"
            onClick={() => onReact(reaction === "up" ? null : "up")}
            className={cn(button, reaction === "up" && "text-foreground")}
            aria-pressed={reaction === "up"}
            title="Good reply"
            aria-label="Good reply"
          >
            <ThumbsUp className={cn("h-3.5 w-3.5", reaction === "up" && "fill-current")} />
          </button>
          <button
            type="button"
            onClick={() => onReact(reaction === "down" ? null : "down")}
            className={cn(button, reaction === "down" && "text-foreground")}
            aria-pressed={reaction === "down"}
            title="Bad reply"
            aria-label="Bad reply"
          >
            <ThumbsDown className={cn("h-3.5 w-3.5", reaction === "down" && "fill-current")} />
          </button>
        </>
      )}
    </div>
  );
};

interface TypewriterProps {
  text: string;
  /** Reveal the text progressively; when false the text is shown at once. */
  animate: boolean;
  onDone?: () => void;
  /** Rendered once the reveal is complete (formatted text, chips...). */
  children: React.ReactNode;
}

// Words per tick and tick length: a reply of ~80 words takes about a second.
const WORDS_PER_TICK = 2;
const TICK_MS = 24;
// Beyond this the reveal would feel slow, so long replies appear at once.
const MAX_ANIMATED_CHARS = 2500;

/**
 * Reveals a reply word by word, then hands over to the fully formatted
 * rendering. Clicking the text skips to the end. If the text grows while
 * revealing (a reply updated in place), the reveal continues from where it is.
 */
export const Typewriter: React.FC<TypewriterProps> = ({ text, animate, onDone, children }) => {
  const shouldAnimate = animate && text.length <= MAX_ANIMATED_CHARS && !prefersReducedMotion();
  const [shownWords, setShownWords] = useState(shouldAnimate ? 0 : Number.MAX_SAFE_INTEGER);
  const words = text.split(/(\s+)/); // keeps the whitespace so the layout does not jump
  const totalWords = words.length;
  const done = shownWords >= totalWords;
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (done) return;
    const timer = setInterval(() => {
      setShownWords((count) => Math.min(count + WORDS_PER_TICK * 2, totalWords)); // ×2: words and the spaces between them
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [done, totalWords]);

  useEffect(() => {
    if (done) onDoneRef.current?.();
  }, [done]);

  if (done) return <>{children}</>;
  return (
    <div
      className="cursor-text whitespace-pre-wrap text-sm text-foreground leading-relaxed"
      onClick={() => setShownWords(Number.MAX_SAFE_INTEGER)}
      title="Click to show the whole reply"
    >
      {words.slice(0, shownWords).join("")}
      <span className="ai-caret" aria-hidden />
    </div>
  );
};
