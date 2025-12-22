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
    className="w-full max-w-2xl bg-white border border-[#e5e7eb] rounded-[26px] relative px-4 py-5"
  >
    <textarea
      rows={1}
      className="w-full h-28 bg-transparent outline-none text-sm text-[#0f172a] placeholder:text-[#71717A] pr-14 pt-15 resize-none leading-5"
      placeholder="Enter an answer"
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
    <button
      type="submit"
      aria-label="Send"
      disabled={disabled || !value.trim()}
      className="w-10 h-10 rounded-xl bg-[#5b4bff] text-white font-bold text-lg grid place-items-center shadow-[0_10px_24px_rgba(91,75,255,0.35)] disabled:opacity-60 disabled:shadow-none absolute bottom-3 right-3"
    >
      <ArrowUp size={16} />
    </button>
  </form>
);