import { eachDayOfInterval, format } from "date-fns";
import type { DateRange } from "react-day-picker";

export const COMPARE_SERIES_SUFFIX = "__compare";

/** Normalize API date strings to `yyyy-MM-dd`. */
export function normalizeDateKey(date: string): string {
  return date.slice(0, 10);
}

export function formatChartDayLabel(dateStr: string): string {
  const d = new Date(normalizeDateKey(dateStr) + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function formatPeriodRangeLabel(range: DateRange | undefined): string | null {
  if (!range?.from || !range?.to) return null;
  return `${format(range.from, "MMM d")} – ${format(range.to, "MMM d")}`;
}

/** Every calendar day in the range (inclusive), as `yyyy-MM-dd`. */
export function enumerateDateRange(range: DateRange | undefined): string[] {
  if (!range?.from || !range?.to) return [];
  const start = range.from <= range.to ? range.from : range.to;
  const end = range.from <= range.to ? range.to : range.from;
  return eachDayOfInterval({ start, end }).map((d) => format(d, "yyyy-MM-dd"));
}

export type RelativePeriodDay = {
  index: number;
  label: string;
  selectedDate: string;
  comparisonDate: string | null;
};

/**
 * GA-style alignment: x-axis days come only from the selected period.
 * Comparison values map by relative index (day 1 vs day 1, etc.).
 */
export function alignPeriodsByRelativeIndex(
  selectedRange: DateRange,
  comparisonRange: DateRange,
): RelativePeriodDay[] {
  const selectedDates = enumerateDateRange(selectedRange);
  const comparisonDates = enumerateDateRange(comparisonRange);

  return selectedDates.map((selectedDate, index) => ({
    index,
    label: formatChartDayLabel(selectedDate),
    selectedDate,
    comparisonDate: comparisonDates[index] ?? null,
  }));
}

export function isCompareSeriesKey(key: string): boolean {
  return key.endsWith(COMPARE_SERIES_SUFFIX);
}

export function compareSeriesKey(baseKey: string): string {
  return `${baseKey}${COMPARE_SERIES_SUFFIX}`;
}

export function compareLegendLabel(metricLabel: string, comparisonRangeLabel: string | null): string {
  if (!comparisonRangeLabel) return `${metricLabel} (comparison)`;
  return `${metricLabel} — Comparison (${comparisonRangeLabel})`;
}
