import { ArrowUp } from "lucide-react";
import { useAutoGrowTextarea, submitOnEnter } from "@/hooks/useAutoGrowTextarea";

interface OnboardingInputProps {
  value: string;
  disabled: boolean;
  onChange: (val: string) => void;
  onSubmit: (event: React.FormEvent) => void;
}

// The 56px bottom padding clears the send button, so the box starts taller than
// one line and grows from there.
const MIN_HEIGHT = 132;

export const OnboardingInput = ({ value, disabled, onChange, onSubmit }: OnboardingInputProps) => {
  const inputRef = useAutoGrowTextarea(value);

  return (
  <form
    onSubmit={onSubmit}
    className="w-full max-w-2xl relative"
  >
    <div className="rounded-2xl border border-border bg-card shadow-sm focus-within:border-ai-brand/30 focus-within:shadow-md focus-within:shadow-ai-brand/5 transition-all duration-200">
      <textarea
        ref={inputRef}
        rows={1}
        style={{ minHeight: MIN_HEIGHT }}
        className="w-full bg-transparent outline-none text-sm text-foreground placeholder:text-muted-foreground px-5 pt-4 pb-14 resize-none leading-relaxed"
        placeholder="Describe what you want your agent to do..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={submitOnEnter(() => inputRef.current?.form?.requestSubmit())}
        disabled={disabled}
      />
      <div className="absolute bottom-3 right-3">
        <button
          type="submit"
          aria-label="Send"
          disabled={disabled || !value.trim()}
          className="h-9 w-9 rounded-xl bg-ai-brand text-white grid place-items-center shadow-lg shadow-ai-brand/25 transition-all duration-150 hover:bg-ai-brand-hover hover:shadow-xl hover:shadow-ai-brand/30 disabled:opacity-40 disabled:shadow-none disabled:bg-slate-400"
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>
    </div>
  </form>
  );
};
