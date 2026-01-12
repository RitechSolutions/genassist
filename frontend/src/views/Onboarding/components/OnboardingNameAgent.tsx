interface OnboardingNameAgentProps {
  value: string;
  disabled?: boolean;
  onChange: (val: string) => void;
  onContinue: () => void;
}

export const OnboardingNameAgent = ({
  value,
  disabled = false,
  onChange,
  onContinue,
}: OnboardingNameAgentProps) => {
  const isButtonDisabled = disabled || !value.trim();

  return (
    <div className="w-full max-w-md text-left space-y-3 animate-fade-up">
      <p className="text-sm text-[#9ca3af]">Fantastic!</p>
      <p className="text-base font-semibold text-[#0f172a]">Finally let&apos;s name your agent.</p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onContinue();
        }}
        className="w-full space-y-3"
      >
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter agent name"
          disabled={disabled}
          className="w-full h-10 rounded-xl border border-[#e5e7eb] bg-white px-4 text-sm text-[#0f172a] outline-none placeholder:text-[#9ca3af] focus:ring-2 focus:ring-[#5b4bff]/30"
        />

        <button
          type="submit"
          disabled={isButtonDisabled}
          className={[
            "h-10 w-32 rounded-xl text-sm font-semibold text-white transition-colors",
            isButtonDisabled
              ? "bg-[#a7a3ff]"
              : "bg-[#5b4bff] shadow-[0_10px_24px_rgba(91,75,255,0.35)] hover:bg-[#4f46e5]",
          ].join(" ")}
        >
          Continue
        </button>
      </form>
    </div>
  );
};