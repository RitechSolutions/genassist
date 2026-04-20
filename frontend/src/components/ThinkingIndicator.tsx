import { AiAvatar } from "@/components/AiAvatar";

/** Animated bouncing-dots indicator shown while the AI is generating a response. */
export const ThinkingIndicator = () => (
  <div className="flex items-start gap-3 animate-fade-up">
    <AiAvatar />
    <div className="flex items-center gap-1 pt-1.5">
      <span className="h-1.5 w-1.5 rounded-full bg-ai-brand animate-bounce" style={{ animationDelay: "0ms" }} />
      <span className="h-1.5 w-1.5 rounded-full bg-ai-brand animate-bounce" style={{ animationDelay: "150ms" }} />
      <span className="h-1.5 w-1.5 rounded-full bg-ai-brand animate-bounce" style={{ animationDelay: "300ms" }} />
    </div>
  </div>
);
