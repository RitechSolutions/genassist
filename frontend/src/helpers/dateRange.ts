import type { DateRange } from "react-day-picker";

/** A picker range with both ends resolved. */
export type NormalizedDateRange = { from: Date; to: Date };

/** Half-open interval of whole local days, ready for UTC conversion. */
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

function localMidnight(day: Date): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate());
}

function utcDateString(instant: Date): string {
  return instant.toISOString().slice(0, 10);
}

export function toExactInterval(
  range: DateRange | undefined,
): ExactInterval | undefined {
  const normalized = normalizeDateRange(range);
  if (!normalized) return undefined;
  const start = localMidnight(normalized.from);
  const endExclusive = localMidnight(normalized.to);
  endExclusive.setDate(endExclusive.getDate() + 1);
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
