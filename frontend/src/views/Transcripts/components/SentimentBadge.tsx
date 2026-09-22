import { AlertCircle, CheckCircle, MinusCircle } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/helpers/utils";

type SentimentStyle = { icon: ReactNode; bg: string; text: string; border: string };

const NEGATIVE_STYLE: SentimentStyle = {
  icon: <AlertCircle className="w-3 h-3" />,
  bg: "bg-rose-50 dark:bg-rose-500/15",
  text: "text-rose-600 dark:text-rose-400",
  border: "border-rose-200 dark:border-rose-500/30",
};

const SENTIMENT_CONFIG: Record<string, SentimentStyle> = {
  positive: {
    icon: <CheckCircle className="w-3 h-3" />,
    bg: "bg-emerald-50 dark:bg-emerald-500/15",
    text: "text-emerald-700 dark:text-emerald-400",
    border: "border-emerald-200 dark:border-emerald-500/30",
  },
  neutral: {
    icon: <MinusCircle className="w-3 h-3" />,
    bg: "bg-amber-50 dark:bg-amber-500/15",
    text: "text-amber-700 dark:text-amber-400",
    border: "border-amber-200 dark:border-amber-500/30",
  },
  negative: NEGATIVE_STYLE,
  "very-bad": NEGATIVE_STYLE,
};

const DEFAULT_SENTIMENT: SentimentStyle = {
  icon: <MinusCircle className="w-3 h-3" />,
  bg: "bg-muted",
  text: "text-muted-foreground",
  border: "border-border",
};

type SentimentBadgeProps = {
  sentiment: string;
  className?: string;
};

/**
 * The conversation sentiment pill. A `<span>` throughout so it stays valid inside the split
 * view's `<button>` rows, and shared with the list view so both stay in step.
 */
export function SentimentBadge({ sentiment, className }: SentimentBadgeProps) {
  const cfg = SENTIMENT_CONFIG[sentiment.toLowerCase()] || DEFAULT_SENTIMENT;

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium capitalize",
        cfg.bg,
        cfg.text,
        cfg.border,
        className
      )}
    >
      {cfg.icon}
      {sentiment}
    </span>
  );
}
