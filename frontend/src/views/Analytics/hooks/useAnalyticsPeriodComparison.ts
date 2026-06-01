import { useMemo } from "react";
import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import {
  getComparisonPeriod,
  type ComparisonPeriodResult,
  type PeriodPreset,
} from "@/helpers/analyticsPeriodComparison";

export function formatComparedWithLabel(comparisonRange: DateRange | undefined): string | null {
  if (!comparisonRange?.from || !comparisonRange?.to) return null;
  return `Compared with ${format(comparisonRange.from, "MMM d")} – ${format(comparisonRange.to, "MMM d")}`;
}

export function useAnalyticsPeriodComparison(
  dateRange: DateRange | undefined,
  periodPreset: PeriodPreset,
): {
  period: ComparisonPeriodResult | null;
  comparisonRange: DateRange | undefined;
  comparedWithLabel: string | null;
} {
  return useMemo(() => {
    const period = dateRange ? getComparisonPeriod(dateRange, periodPreset) : null;
    const comparisonRange = period?.comparisonRange;
    return {
      period,
      comparisonRange,
      comparedWithLabel: formatComparedWithLabel(comparisonRange),
    };
  }, [
    dateRange?.from?.getTime(),
    dateRange?.to?.getTime(),
    periodPreset,
  ]);
}
