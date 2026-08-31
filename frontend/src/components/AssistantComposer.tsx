import { ArrowUp, Sparkles } from "lucide-react";

import { cn } from "@/helpers/utils";

type AssistantComposerProps = {
  value: string;
  onChange: (value: string) => void;
  /** Receives the trimmed message; the composer clears the field itself. */
  onSubmit: (message: string) => void;
  placeholder?: string;
  /** Blocks typing and sending while the assistant is answering. */
  busy?: boolean;
  className?: string;
};

/**
 * The message box for the assistant surfaces: one rounded field with the send control inside it.
 * Shared by the workflow builder's Conversational tab and the conversation detail's Ask GenAI
 * pane so both compose messages the same way.
 */
export function AssistantComposer({
  value,
  onChange,
  onSubmit,
  placeholder = "Ask GenAI...",
  busy = false,
  className,
}: AssistantComposerProps) {
  const canSend = value.trim().length > 0 && !busy;

  const submit = () => {
    if (!canSend) return;
    onSubmit(value.trim());
    onChange("");
  };

  return (
    <div className={cn("relative flex items-center", className)}>
      <Sparkles
        className="pointer-events-none absolute left-3 h-4 w-4 text-[hsl(var(--brand-600))]"
        aria-hidden
      />
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        placeholder={placeholder}
        disabled={busy}
        className="h-10 w-full rounded-full border border-[hsl(var(--brand-600))] bg-card pl-9 pr-11 text-sm transition-all placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[hsl(var(--brand-600))]/30 disabled:opacity-50"
      />
      <button
        type="button"
        onClick={submit}
        disabled={!canSend}
        aria-label="Send message"
        className="absolute right-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-[hsl(var(--brand-600))] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:opacity-100 dark:disabled:bg-zinc-700"
      >
        <ArrowUp className="h-3.5 w-3.5 text-white" aria-hidden />
      </button>
    </div>
  );
}
