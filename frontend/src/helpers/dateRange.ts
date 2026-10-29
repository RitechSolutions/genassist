import { format, subDays } from "date-fns";
import type { DateRange } from "react-day-picker";

/** A picker range with both ends resolved. */
export type NormalizedDateRange = { from: Date; to: Date };

/** Half-open interval of whole UTC days. */
export type ExactInterval = { start: Date; endExclusive: Date };

export type ExactActivityParams = {
  activity_from_datetime?: string;
  activity_to_datetime?: string;
};

export type UtcBucketDateParams = {
  from_date?: string;
  to_date?: string;
};

/**
 * Turns a picker selection into a date range. A single click (`{ from, to: undefined }`)
 * means just that one day; no selection at all stays undefined, meaning all-time.
 */
export function normalizeDateRange(
  range: DateRange | undefined,
): NormalizedDateRange | undefined {
  if (!range?.from) return undefined;
  return { from: range.from, to: range.to ?? range.from };
}

function utcMidnight(day: Date): Date {
  return new Date(Date.UTC(day.getFullYear(), day.getMonth(), day.getDate()));
}

function utcDateString(instant: Date): string {
  return instant.toISOString().slice(0, 10);
}

/** The picked calendar day at UTC midnight. */
export function utcDayStart(day: Date): string {
  return utcMidnight(day).toISOString();
}

/** Last microsecond of the picked calendar day in UTC. */
export function utcDayEnd(day: Date): string {
  return `${format(day, "yyyy-MM-dd")}T23:59:59.999999Z`;
}

export function toExactInterval(
  range: DateRange | undefined,
): ExactInterval | undefined {
  const normalized = normalizeDateRange(range);
  if (!normalized) return undefined;
  const start = utcMidnight(normalized.from);
  const endExclusive = utcMidnight(normalized.to);
  endExclusive.setUTCDate(endExclusive.getUTCDate() + 1);
  return { start, endExclusive };
}

/** Exact conversation-activity boundaries as UTC ISO strings. */
export function toExactActivityParams(
  range: DateRange | undefined,
): ExactActivityParams {
  const interval = toExactInterval(range);
  if (!interval) return {};
  return {
    activity_from_datetime: interval.start.toISOString(),
    activity_to_datetime: interval.endExclusive.toISOString(),
  };
}

export function toUtcBucketDateParams(
  range: DateRange | undefined,
): UtcBucketDateParams {
  const interval = toExactInterval(range);
  if (!interval) return {};
  return {
    from_date: utcDateString(interval.start),
    to_date: utcDateString(new Date(interval.endExclusive.getTime() - 1)),
  };
}

/** Calendar days in local time for BaseFilterModel filters, last day included */
export function toInclusiveDateParams(range: DateRange | undefined): {
  from_date?: string;
  to_date?: string;
} {
  const params: { from_date?: string; to_date?: string } = {};
  if (range?.from) params.from_date = format(range.from, "yyyy-MM-dd");
  if (range?.to) params.to_date = format(range.to, "yyyy-MM-dd 23:59:59");
  return params;
}

export function dashboardDefaultDateRange(): DateRange {
  return { from: subDays(new Date(), 30), to: new Date() };
}

export function formatDateRangeLabel(from: Date, to: Date): string {
  return `${format(from, "MMM d")} – ${format(to, "MMM d, yyyy")}`;
}
