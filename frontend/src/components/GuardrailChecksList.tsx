import { cn } from "@/helpers/utils";
import {
  guardrailCheckLabel,
  guardrailStageLabel,
} from "@/helpers/guardrailChecks";
import {
  GuardrailAction,
  GuardrailVerdict,
} from "@/interfaces/guardrails.interface";

const ACTION_BADGES: Record<GuardrailAction, { label: string; className: string }> =
  {
    passed: {
      label: "Passed",
      className:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400",
    },
    flagged: {
      label: "Flagged",
      className:
        "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400",
    },
    blocked: {
      label: "Blocked",
      className:
        "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-400",
    },
    error: {
      label: "Check failed",
      className: "bg-muted text-muted-foreground",
    },
    skipped: {
      label: "Not fully checked",
      className: "bg-muted text-muted-foreground",
    },
  };

export function GuardrailChecksList({
  verdicts,
  className,
}: {
  verdicts: GuardrailVerdict[];
  className?: string;
}) {
  return (
    <ul
      aria-label="Check results"
      className={cn("divide-y divide-border rounded-lg border", className)}
    >
      {verdicts.map((verdict, i) => {
        const badge = ACTION_BADGES[verdict.action] ?? ACTION_BADGES.error;
        return (
          <li
            key={`${verdict.stage}-${verdict.check_type}-${verdict.category}-${i}`}
            className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
          >
            <div className="min-w-0">
              <div className="truncate font-medium text-foreground">
                {guardrailCheckLabel(verdict)}
              </div>
              <div className="text-xs text-muted-foreground">
                {guardrailStageLabel(verdict.stage)}
                {typeof verdict.score === "number" &&
                  ` · Score ${verdict.score}`}
              </div>
            </div>
            <span
              className={cn(
                "shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold",
                badge.className
              )}
            >
              {badge.label}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
