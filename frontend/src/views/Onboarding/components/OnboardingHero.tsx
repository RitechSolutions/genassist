import { Sparkles } from "lucide-react";

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
  <div className="w-full max-w-2xl text-center space-y-5 animate-fade-up">
    {/* AI avatar */}
    <div className="flex justify-center">
      <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-[#5b4bff] to-[#8b5cf6] flex items-center justify-center shadow-lg shadow-[#5b4bff]/20">
        <Sparkles className="h-6 w-6 text-white" />
      </div>
    </div>

    {/* Congrats badge */}
    <div
      className={`overflow-hidden transition-all duration-300 ease-out ${
        showCongrats ? "max-h-8 opacity-100" : "max-h-0 opacity-0"
      }`}
    >
      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#eef2ff] px-3 py-1 text-xs font-semibold text-[#4f46e5]">
        Congratulations!
      </span>
    </div>

    {/* Title */}
    <h1 className="text-2xl font-bold text-[#0f172a] tracking-tight">{title}</h1>

    {/* Subtitle / agent reply */}
    <p className="text-[15px] text-[#64748b] leading-relaxed max-w-lg mx-auto">{subtitle}</p>

    {/* Quick actions */}
    {showQuickActions && quickActions.length > 0 && (
      <div className="pt-2 flex flex-col items-center gap-2.5">
        {quickActions.map((action, index) => (
          <button
            key={action}
            type="button"
            onClick={() => onQuickAction(action)}
            disabled={disableQuickActions}
            className="group inline-flex items-center gap-3 rounded-xl border border-[#e2e8f0] bg-white px-4 py-2.5 text-left shadow-sm transition-all duration-150 hover:border-[#5b4bff]/30 hover:shadow-md hover:shadow-[#5b4bff]/5 disabled:opacity-50 disabled:hover:border-[#e2e8f0] disabled:hover:shadow-sm animate-fade-up"
            style={{ animationDelay: `${index * 80}ms` }}
          >
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-[#f1f5f9] text-xs font-semibold text-[#64748b] group-hover:bg-[#eef2ff] group-hover:text-[#5b4bff] transition-colors">
              {index + 1}
            </span>
            <span className="text-sm font-medium text-[#334155] group-hover:text-[#0f172a] transition-colors">
              {action}
            </span>
          </button>
        ))}
      </div>
    )}
  </div>
);
