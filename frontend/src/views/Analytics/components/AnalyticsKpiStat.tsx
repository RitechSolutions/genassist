import type { ReactNode } from "react";
import { Tooltip } from "@/components/tooltip";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/helpers/utils";

export interface AnalyticsKpiStatProps {
  label: string;
  value: string;
  sub?: string;
  description?: string;
  valueClassName?: string;
  icon?: LucideIcon;
  iconColor?: string;
  delta?: ReactNode;
  /** @deprecated Dividers are handled by grid spacing; kept for call-site compatibility */
  showDivider?: boolean;
}

/** Single KPI cell — value stays on one line; labels and subtext wrap in narrow columns. */
export function AnalyticsKpiStat({
  label,
  value,
  sub,
  description,
  valueClassName,
  icon: Icon,
  iconColor,
  delta,
}: AnalyticsKpiStatProps) {
  return (
    <div className="flex min-w-0 flex-col gap-1 py-1">
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span
          className={cn(
            "text-xl font-bold leading-tight tabular-nums sm:text-2xl",
            valueClassName ?? "text-foreground",
          )}
        >
          {value}
        </span>
        {delta}
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-x-1 gap-y-0.5 text-xs font-medium leading-snug text-muted-foreground sm:text-sm">
        {Icon && (
          <Icon
            className="h-3.5 w-3.5 shrink-0"
            style={iconColor ? { color: iconColor } : undefined}
            aria-hidden
          />
        )}
        <span className="min-w-0 break-words">{label}</span>
        {description && (
          <Tooltip
            content={
              <span className="block max-w-[200px] whitespace-normal">{description}</span>
            }
            iconClassName="h-3 w-3 shrink-0"
            contentClassName="w-48 text-center"
          />
        )}
      </div>
      {sub && (
        <p className="min-w-0 text-xs leading-snug text-muted-foreground/70 tabular-nums break-words">
          {sub}
        </p>
      )}
    </div>
  );
}

/** Responsive grid for 4–5 KPI metrics (AI Insights + Agent Performance summary). */
export function analyticsKpiGridClass(metricCount: number): string {
  if (metricCount >= 5) {
    return cn(
      "grid min-w-0 grid-cols-2 gap-x-4 gap-y-5",
      "sm:gap-x-6 sm:gap-y-6",
      "md:grid-cols-3",
      "xl:grid-cols-5 xl:gap-x-5",
      "2xl:gap-x-8",
    );
  }
  if (metricCount === 4) {
    return cn(
      "grid min-w-0 grid-cols-2 gap-x-4 gap-y-5",
      "sm:gap-x-6 sm:gap-y-6",
      "lg:grid-cols-4 lg:gap-y-4",
    );
  }
  return "grid min-w-0 grid-cols-2 gap-4 sm:grid-cols-3 sm:gap-6";
}
