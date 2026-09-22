import { Sparkles } from "lucide-react";

import { cn } from "@/helpers/utils";

/**
 * The GenAssist spark mark. Paints with `currentColor` so it can sit on light and dark
 * surfaces alike — the default matches the flat grey it was originally drawn with.
 */
export function GenAssistMark({ className, ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className={cn("text-zinc-300 dark:text-zinc-700", className)}
      {...props}
    >
      <path
        d="M59.9971 32.8848L59.999 32.8867L35.1133 57.7705L22.3008 44.96L22.915 43.3008C23.6078 41.431 24.8249 39.8283 26.3906 38.6611L35.1133 47.3838V32.8848H59.9971ZM20.3867 23.3965C21.2165 25.6369 22.6409 27.5756 24.4727 29.0283L20.6152 32.8867L24.4668 36.7383C22.6377 38.1905 21.2157 40.128 20.3867 42.3662L20.2031 42.8613L10.2266 32.8867L20.2051 22.9072L20.3867 23.3965ZM57.4336 30.3203H47.0449L35.1133 18.3877L26.3965 27.1045C24.8278 25.9367 23.6084 24.3323 22.915 22.46L22.3037 20.8086L35.1133 8L57.4336 30.3203Z"
        fill="currentColor"
      />
      <path
        d="M18.5165 18.3594L20.3777 23.3911C21.6857 26.9231 24.4693 29.7066 28.0013 31.0147L33.033 32.8759L28.0013 34.737C24.4693 36.045 21.6858 38.8287 20.3777 42.3607L18.5165 47.3924L16.6554 42.3607C15.3474 38.8287 12.5637 36.0451 9.03169 34.737L4 32.8759L9.03169 31.0147C12.5637 29.7067 15.3473 26.9231 16.6554 23.3911L18.5165 18.3594Z"
        fill="currentColor"
      />
    </svg>
  );
}

export type AssistantSuggestion = {
  label: string;
  onSelect: () => void;
};

type AssistantEmptyStateProps = {
  /** Muted opening line. */
  title: string;
  /** The question put to the user, in bold. */
  prompt: string;
  /** One-click openers, so the user does not have to think of a first question. */
  suggestions?: AssistantSuggestion[];
  className?: string;
};

/**
 * Shared opening screen for the assistant surfaces — the workflow builder's Conversational tab
 * and the conversation detail's Ask GenAI pane — so they keep the same first impression.
 */
export function AssistantEmptyState({
  title,
  prompt,
  suggestions,
  className,
}: AssistantEmptyStateProps) {
  return (
    <div
      className={cn(
        "flex h-full flex-col items-center justify-center gap-8 py-12 text-center",
        className
      )}
    >
      <GenAssistMark />
      <div className="space-y-4">
        <div className="space-y-1">
          <p className="text-lg text-muted-foreground">{title}</p>
          <p className="text-lg font-semibold text-foreground">{prompt}</p>
        </div>
        {suggestions && suggestions.length > 0 && (
          <div className="flex flex-wrap justify-center gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.label}
                type="button"
                onClick={suggestion.onSelect}
                className="group inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3.5 py-1.5 text-sm text-foreground shadow-sm ring-offset-background transition-colors hover:border-primary/40 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <Sparkles
                  className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
                  aria-hidden
                />
                {suggestion.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
