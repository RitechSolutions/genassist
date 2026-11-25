import { format, subDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { dateParts, readTimeZoneMode } from "@/helpers/timeZone";

/** A picker range with both ends resolved. */
export type NormalizedDateRange = { from: Date; to: Date };

/** Half-open interval of whole calendar days. */
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

/** Today in the active zone, as the local-midnight Date the picker uses. */
export function calendarToday(now: Date = new Date()): Date {
  const { year, month, day } = dateParts(now);
  return new Date(year, month, day);
}

export function lastDaysDateRange(days: number): DateRange {
  const today = calendarToday();
  return { from: subDays(today, days), to: today };
}

function dayStart(day: Date, plusDays = 0): Date {
  const y = day.getFullYear();
  const m = day.getMonth();
  const d = day.getDate() + plusDays;
  return readTimeZoneMode() === "utc"
    ? new Date(Date.UTC(y, m, d))
    : new Date(y, m, d);
}

function utcDateString(instant: Date): string {
  return instant.toISOString().slice(0, 10);
}

/** The picked calendar day at midnight in the active zone. */
export function dayStartIso(day: Date): string {
  return dayStart(day).toISOString();
}

/** Last microsecond of the picked calendar day in the active zone. */
export function dayEndIso(day: Date): string {
  const lastSecond = new Date(dayStart(day, 1).getTime() - 1000);
  return `${lastSecond.toISOString().slice(0, 19)}.999999Z`;
}

export function toExactInterval(
  range: DateRange | undefined,
): ExactInterval | undefined {
  const normalized = normalizeDateRange(range);
  if (!normalized) return undefined;
  return {
    start: dayStart(normalized.from),
    endExclusive: dayStart(normalized.to, 1),
  };
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
  return lastDaysDateRange(30);
}

export function formatDateRangeLabel(from: Date, to: Date): string {
  return `${format(from, "MMM d")} – ${format(to, "MMM d, yyyy")}`;
}
