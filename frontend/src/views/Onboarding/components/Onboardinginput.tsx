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
    <div className="rounded-2xl border border-[#e2e8f0] bg-white shadow-sm focus-within:border-[#5b4bff]/30 focus-within:shadow-md focus-within:shadow-[#5b4bff]/5 transition-all duration-200">
      <textarea
        rows={1}
        className="w-full min-h-[100px] bg-transparent outline-none text-sm text-[#0f172a] placeholder:text-[#94a3b8] px-5 pt-4 pb-14 resize-none leading-relaxed"
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
          className="h-9 w-9 rounded-xl bg-[#5b4bff] text-white grid place-items-center shadow-lg shadow-[#5b4bff]/25 transition-all duration-150 hover:bg-[#4f46e5] hover:shadow-xl hover:shadow-[#5b4bff]/30 disabled:opacity-40 disabled:shadow-none disabled:bg-[#94a3b8]"
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>
    </div>
  </form>
);
