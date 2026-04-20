import { ArrowUp } from "lucide-react";

interface OnboardingInputProps {
  value: string;
  disabled: boolean;
  onChange: (val: string) => void;
  onSubmit: (event: React.FormEvent) => void;
}

export const OnboardingInput = ({ value, disabled, onChange, onSubmit }: OnboardingInputProps) => (
  <form
    onSubmit={onSubmit}
    className="w-full max-w-2xl relative"
  >
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm focus-within:border-ai-brand/30 focus-within:shadow-md focus-within:shadow-ai-brand/5 transition-all duration-200">
      <textarea
        rows={1}
        className="w-full min-h-[100px] bg-transparent outline-none text-sm text-slate-900 placeholder:text-slate-400 px-5 pt-4 pb-14 resize-none leading-relaxed"
        placeholder="Describe what you want your agent to do..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            e.currentTarget.form?.requestSubmit();
          }
        }}
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
