interface OnboardingHeroProps {
  showCongrats: boolean;
  showQuickActions: boolean;
  subtitle: string;
  title: string;
  quickActions: string[];
  onQuickAction: (message: string) => void;
  disableQuickActions?: boolean;
}

export const OnboardingHero = ({
  showCongrats,
  showQuickActions,
  subtitle,
  title,
  quickActions,
  onQuickAction,
  disableQuickActions = false,
}: OnboardingHeroProps) => (
  <div className="w-full max-w-2xl text-left space-y-2 animate-fade-up">
    <p
      className={`overflow-hidden text-base font-semibold text-[#4f46e5] transition-all duration-200 ease-out ${
        showCongrats ? "max-h-5 opacity-100 translate-y-0" : "max-h-0 opacity-0 -translate-y-1"
      }`}
    >
      🎉 Congratulations!
    </p>
    <p className="text-[15px] text-[#6b7280] transition-colors duration-1200">{subtitle}</p>
    <p className="text-lg font-semibold text-[#0f172a]">{title}</p>

    {showQuickActions && (
      <div className="pt-4 flex flex-col gap-3">
        {quickActions.map((action, index) => (
          <button
            key={action}
            type="button"
            onClick={() => onQuickAction(action)}
            disabled={disableQuickActions}
            className="group inline-flex w-fit items-center gap-3 rounded-full bg-gray-100 px-2 py-1 text-left shadow-sm transition-all duration-1200 hover:bg-gray-200 disabled:opacity-60 disabled:shadow-none disabled:bg-gray-200 animate-fade-up"
          >
            <span className="grid h-6 w-6 place-items-center border border-gray-300 rounded-full text-xs font-semibold">
              {index + 1}
            </span>
            <span className="text-sm font-semibold text-[#111827]">{action}</span>
          </button>
        ))}
      </div>
    )}
  </div>
);