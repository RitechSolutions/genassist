import { useEffect, useRef, useState } from "react";
import { ArrowRight, Reply } from "lucide-react";

import { AssistantComposer } from "@/components/AssistantComposer";
import { GenAssistMark } from "@/components/AssistantEmptyState";
import FormattedText from "@/components/FormattedText";
import { HoverGrid } from "@/components/HoverGrid";
import { cn } from "@/helpers/utils";
import { QuestionCard } from "@/views/AIAgents/Workflows/components/panels/AssistantMessageExtras";
import { MessageActions, ReasoningTrail, Typewriter, WorkSummary } from "@/views/AIAgents/Workflows/components/panels/AssistantMotion";
import type { LiveTurn } from "@/views/AIAgents/Workflows/utils/assistantDraft";
import { BUILDER_EXAMPLES, EXAMPLES_PREVIEW_COUNT } from "@/views/AIAgents/Workflows/utils/builderExamples";
import { BUILDER_MESSAGE_MAX_CHARS } from "@/views/AIAgents/Workflows/utils/builderLimits";
import type { OnboardingMessage } from "@/views/Onboarding/hooks/useOnboardingChat";

interface OnboardingChatProps {
  title: string;
  messages: OnboardingMessage[];
  isThinking: boolean;
  liveTurn: LiveTurn | null;
  /** Openers from the agent's welcome data; the built-in examples are used when there are none. */
  welcomeFaqs: string[];
  /** Answers the agent offered in its latest reply (interactive options), one click sends one. */
  replyOptions: string[];
  prompt: string;
  onPromptChange: (value: string) => void;
  onSend: (message: string) => void;
  onAnswer: (messageIndex: number, answer: string) => void;
  onReact: (messageIndex: number, reaction: "up" | "down" | null) => void;
  disabled: boolean;
}

/**
 * The onboarding conversation with the Workflow Builder, laid out like the
 * canvas assistant in full screen: one big box in the middle to start, then a
 * centred thread with the builder's reasoning, its question cards and the
 * composer at the bottom.
 */
export const OnboardingChat = ({
  title,
  messages,
  isThinking,
  liveTurn,
  welcomeFaqs,
  replyOptions,
  prompt,
  onPromptChange,
  onSend,
  onAnswer,
  onReact,
  disabled,
}: OnboardingChatProps) => {
  const [showAllExamples, setShowAllExamples] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Replies already revealed; a re-render must not type them out again.
  const revealedRef = useRef<Set<number>>(new Set());
  const isEmptyChat = messages.length === 0 && !isThinking;

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isThinking, liveTurn]);

  const examples = welcomeFaqs.length
    ? welcomeFaqs.map((faq) => ({ label: faq, prompt: faq, icon: undefined }))
    : BUILDER_EXAMPLES.map((example) => ({ ...example }));
  const visibleExamples = showAllExamples ? examples : examples.slice(0, EXAMPLES_PREVIEW_COUNT);

  const composer = (hero: boolean) => (
    <AssistantComposer
      value={prompt}
      onChange={onPromptChange}
      onSubmit={onSend}
      size={hero ? "hero" : "inline"}
      autoFocus={hero}
      placeholder={hero ? "Tell me what to build or ask a question" : "Reply to the builder..."}
      busy={disabled}
      maxLength={BUILDER_MESSAGE_MAX_CHARS}
    />
  );

  if (isEmptyChat) {
    return (
      <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden px-5 pb-16 pt-6">
        <HoverGrid className="absolute inset-x-0 bottom-0 h-[36%] [mask-image:linear-gradient(to_bottom,transparent,black_40%)]" />
        <div className="ai-rise-in relative z-10 w-full max-w-[680px]">
          <h1 className="mb-6 flex items-center justify-center gap-2.5 text-center text-[22px] font-semibold tracking-tight text-foreground">
            <GenAssistMark className="h-8 w-8 text-zinc-700 dark:text-white" />
            {title}
          </h1>
          {composer(true)}
          <div
            aria-hidden={prompt.trim().length > 0}
            className={cn(
              "mt-4 flex flex-wrap items-center justify-center gap-1.5 transition-all duration-300 ease-in-out",
              prompt.trim() ? "pointer-events-none translate-y-2 opacity-0" : "translate-y-0 opacity-100"
            )}
          >
            {visibleExamples.map((example) => (
              <button
                key={example.label}
                type="button"
                disabled={disabled}
                onClick={() => onPromptChange(example.prompt)}
                title={example.prompt}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-3 py-1.5 text-xs text-foreground transition-colors hover:border-[hsl(var(--brand-600))]/50 hover:bg-[hsl(var(--brand-600))]/5 disabled:opacity-50"
              >
                {example.icon && <example.icon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />}
                {example.label}
              </button>
            ))}
            {examples.length > EXAMPLES_PREVIEW_COUNT && (
              <button
                type="button"
                onClick={() => setShowAllExamples((value) => !value)}
                className="inline-flex items-center gap-1 px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                {showAllExamples ? "Show less" : "See all"}
                <ArrowRight className={cn("h-3 w-3 transition-transform", showAllExamples && "rotate-90")} />
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const lastIndex = messages.length - 1;
  return (
    <div className="flex h-full w-full flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <div className="mx-auto w-full max-w-3xl space-y-5">
          {messages.map((msg, index) =>
            msg.role === "user" ? (
              <div key={index} className="flex justify-end">
                <div className="max-w-[82%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-[hsl(var(--brand-600))] px-4 py-2.5 text-sm text-white shadow-sm">
                  {msg.text}
                </div>
              </div>
            ) : (
              <div key={index} className="min-w-0">
                <WorkSummary steps={msg.steps} workedMs={msg.workedMs} />
                <div className="text-sm leading-relaxed text-foreground">
                  <Typewriter
                    text={msg.text}
                    animate={!msg.streamed && index === lastIndex && !revealedRef.current.has(index)}
                    onDone={() => revealedRef.current.add(index)}
                  >
                    <FormattedText text={msg.text} />
                  </Typewriter>
                </div>
                {msg.question && (
                  <QuestionCard
                    question={msg.question}
                    answer={msg.answer}
                    disabled={disabled || index !== lastIndex}
                    onAnswer={(answer) => onAnswer(index, answer)}
                  />
                )}
                {index === lastIndex && !msg.question && replyOptions.length > 0 && !isThinking && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {replyOptions.map((option) => (
                      <button
                        key={option}
                        type="button"
                        disabled={disabled}
                        onClick={() => onSend(option)}
                        className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-3 py-1.5 text-xs text-foreground transition-colors hover:border-[hsl(var(--brand-600))]/50 hover:bg-[hsl(var(--brand-600))]/5 disabled:opacity-50"
                      >
                        <Reply className="h-3 w-3 text-muted-foreground" aria-hidden />
                        {option}
                      </button>
                    ))}
                  </div>
                )}
                {msg.text.trim() && (
                  <MessageActions text={msg.text} reaction={msg.reaction} onReact={(reaction) => onReact(index, reaction)} />
                )}
              </div>
            )
          )}
          {isThinking && <ReasoningTrail turn={liveTurn} />}
        </div>
      </div>
      {/* Clears the footer laid over the bottom of the page. */}
      <div className="mx-auto w-full max-w-3xl px-4 pb-12">{composer(false)}</div>
    </div>
  );
};
