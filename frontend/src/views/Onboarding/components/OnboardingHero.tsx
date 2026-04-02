import { useEffect, useRef } from "react";
import { Sparkles, User } from "lucide-react";
import { type OnboardingMessage } from "@/views/Onboarding/hooks/useOnboardingChat";

/** Lightweight markdown-ish renderer for agent messages (bold, numbered lists, bullet lists). */
const FormattedText = ({ text }: { text: string }) => {
  const lines = text.split("\n");

  const renderInline = (line: string, key: number) => {
    // Split on **bold** markers
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    return (
      <span key={key}>
        {parts.map((part, i) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
          }
          return <span key={i}>{part}</span>;
        })}
      </span>
    );
  };

  // Group consecutive list lines into <ol> or <ul>
  const elements: React.ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const orderedMatch = line.match(/^\d+\.\s+(.*)/);
    const bulletMatch = line.match(/^[-•]\s+(.*)/);

    if (orderedMatch) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ""));
        i++;
      }
      elements.push(
        <ol key={elements.length} className="list-decimal list-inside space-y-1 my-1">
          {items.map((item, j) => <li key={j}>{renderInline(item, j)}</li>)}
        </ol>
      );
    } else if (bulletMatch) {
      const items: string[] = [];
      while (i < lines.length && /^[-•]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-•]\s+/, ""));
        i++;
      }
      elements.push(
        <ul key={elements.length} className="list-disc list-inside space-y-1 my-1">
          {items.map((item, j) => <li key={j}>{renderInline(item, j)}</li>)}
        </ul>
      );
    } else if (line.trim() === "") {
      elements.push(<br key={elements.length} />);
      i++;
    } else {
      elements.push(<p key={elements.length} className="my-0.5">{renderInline(line, 0)}</p>);
      i++;
    }
  }

  return <div className="space-y-0.5">{elements}</div>;
};

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

const AiAvatar = () => (
  <div className="h-7 w-7 shrink-0 rounded-lg bg-gradient-to-br from-[#5b4bff] to-[#8b5cf6] flex items-center justify-center shadow-sm shadow-[#5b4bff]/15">
    <Sparkles className="h-3.5 w-3.5 text-white" />
  </div>
);

const UserAvatar = () => (
  <div className="h-7 w-7 shrink-0 rounded-lg bg-[#f1f5f9] flex items-center justify-center">
    <User className="h-3.5 w-3.5 text-[#64748b]" />
  </div>
);

const ThinkingIndicator = () => (
  <div className="flex items-start gap-3 animate-fade-up">
    <AiAvatar />
    <div className="flex items-center gap-1 pt-1.5">
      <span className="h-1.5 w-1.5 rounded-full bg-[#5b4bff] animate-bounce" style={{ animationDelay: "0ms" }} />
      <span className="h-1.5 w-1.5 rounded-full bg-[#5b4bff] animate-bounce" style={{ animationDelay: "150ms" }} />
      <span className="h-1.5 w-1.5 rounded-full bg-[#5b4bff] animate-bounce" style={{ animationDelay: "300ms" }} />
    </div>
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
          <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-[#5b4bff] to-[#8b5cf6] flex items-center justify-center shadow-lg shadow-[#5b4bff]/20">
            <Sparkles className="h-6 w-6 text-white" />
          </div>
        </div>
      )}

      {/* Congrats badge */}
      {!hasMessages && (
        <div
          className={`overflow-hidden transition-all duration-300 ease-out ${
            showCongrats ? "max-h-8 opacity-100" : "max-h-0 opacity-0"
          }`}
        >
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#eef2ff] px-3 py-1 text-xs font-semibold text-[#4f46e5]">
            Congratulations!
          </span>
        </div>
      )}

      {/* Title */}
      <h1 className="text-2xl font-bold text-[#0f172a] tracking-tight">{title}</h1>

      {/* Welcome subtitle — only before conversation starts */}
      {!hasMessages && (
        <p className="text-[15px] text-[#64748b] leading-relaxed max-w-lg mx-auto">{subtitle}</p>
      )}

      {/* Chat thread */}
      {hasMessages && (
        <div ref={scrollRef} className="space-y-4 text-left max-h-[40vh] overflow-y-auto px-1">
          {messages.map((msg, index) =>
            msg.role === "user" ? (
              <div key={index} className="flex items-start gap-3 justify-end animate-fade-up">
                <div className="rounded-2xl rounded-tr-md bg-[#5b4bff] px-4 py-2.5 max-w-[85%]">
                  <p className="text-sm text-white leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                </div>
                <UserAvatar />
              </div>
            ) : (
              <div key={index} className="flex items-start gap-3 animate-fade-up">
                <AiAvatar />
                <div className="rounded-2xl rounded-tl-md bg-white border border-[#e2e8f0] px-4 py-2.5 max-w-[85%] shadow-sm">
                  <div className="text-sm text-[#334155] leading-relaxed">
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
};
