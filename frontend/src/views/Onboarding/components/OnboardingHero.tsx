import { useEffect, useRef } from "react";
import { User } from "lucide-react";
import { type OnboardingMessage } from "@/views/Onboarding/hooks/useOnboardingChat";
import { AiAvatar } from "@/components/AiAvatar";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";
import FormattedText from "@/components/FormattedText";

interface OnboardingHeroProps {
  showCongrats: boolean;
  showQuickActions: boolean;
  subtitle: string;
  title: string;
  quickActions: string[];
  onQuickAction: (message: string) => void;
  disableQuickActions?: boolean;
  messages: OnboardingMessage[];
  isThinking: boolean;
}

const UserAvatar = () => (
  <div className="h-7 w-7 shrink-0 rounded-lg bg-slate-100 flex items-center justify-center">
    <User className="h-3.5 w-3.5 text-slate-500" />
  </div>
);

export const OnboardingHero = ({
  showCongrats,
  showQuickActions,
  subtitle,
  title,
  quickActions,
  onQuickAction,
  disableQuickActions = false,
  messages,
  isThinking,
}: OnboardingHeroProps) => {
  const hasMessages = messages.length > 0;
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change or thinking starts
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isThinking]);

  return (
    <div className="w-full max-w-2xl text-center space-y-5 animate-fade-up">
      {/* AI avatar — only show when no messages yet */}
      {!hasMessages && (
        <div className="flex justify-center">
          <AiAvatar size="lg" />
        </div>
      )}

      {/* Congrats badge */}
      {!hasMessages && (
        <div
          className={`overflow-hidden transition-all duration-300 ease-out ${
            showCongrats ? "max-h-8 opacity-100" : "max-h-0 opacity-0"
          }`}
        >
          <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-600">
            Congratulations!
          </span>
        </div>
      )}

      {/* Title */}
      <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h1>

      {/* Welcome subtitle — only before conversation starts */}
      {!hasMessages && (
        <p className="text-[15px] text-slate-500 leading-relaxed max-w-lg mx-auto">{subtitle}</p>
      )}

      {/* Chat thread */}
      {hasMessages && (
        <div ref={scrollRef} role="log" aria-live="polite" className="space-y-4 text-left max-h-[40vh] overflow-y-auto px-1">
          {messages.map((msg, index) =>
            msg.role === "user" ? (
              <div key={index} className="flex items-start gap-3 justify-end animate-fade-up">
                <div className="rounded-2xl rounded-tr-md bg-ai-brand px-4 py-2.5 max-w-[85%]">
                  <p className="text-sm text-white leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                </div>
                <UserAvatar />
              </div>
            ) : (
              <div key={index} className="flex items-start gap-3 animate-fade-up">
                <AiAvatar />
                <div className="rounded-2xl rounded-tl-md bg-white border border-slate-200 px-4 py-2.5 max-w-[85%] shadow-sm">
                  <div className="text-sm text-slate-700 leading-relaxed">
                    <FormattedText text={msg.text} />
                  </div>
                </div>
              </div>
            ),
          )}
          {isThinking && <ThinkingIndicator />}
        </div>
      )}

      {/* Quick actions */}
      {showQuickActions && quickActions.length > 0 && (
        <div className="pt-2 flex flex-col items-center gap-2.5">
          {quickActions.map((action, index) => (
            <button
              key={action}
              type="button"
              onClick={() => onQuickAction(action)}
              disabled={disableQuickActions}
              className="group inline-flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-left shadow-sm transition-all duration-150 hover:border-ai-brand/30 hover:shadow-md hover:shadow-ai-brand/5 disabled:opacity-50 disabled:hover:border-slate-200 disabled:hover:shadow-sm animate-fade-up"
              style={{ animationDelay: `${index * 80}ms` }}
            >
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-500 group-hover:bg-indigo-50 group-hover:text-ai-brand transition-colors">
                {index + 1}
              </span>
              <span className="text-sm font-medium text-slate-700 group-hover:text-slate-900 transition-colors">
                {action}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
