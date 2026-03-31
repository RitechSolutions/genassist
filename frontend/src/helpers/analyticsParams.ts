import { format } from "date-fns";
import type { DateRange } from "react-day-picker";

export type MetricsApiParams = {
  from_date?: string;
  to_date?: string;
  agent_id?: string;
  compare?: string;
};

/**
 * Convert a local date to the start-of-day in UTC (ISO 8601).
 * E.g. March 30 00:00 Pacific (UTC-7) → "2025-03-30T07:00:00Z"
 */
function localStartOfDayUTC(d: Date): string {
  const start = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0);
  return start.toISOString();
}

/**
 * Convert a local date to the end-of-day in UTC (ISO 8601).
 * E.g. March 30 23:59:59.999 Pacific (UTC-7) → "2025-03-31T06:59:59Z"
 */
function localEndOfDayUTC(d: Date): string {
  const end = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 0);
  return end.toISOString();
}

/**
 * Convert a local date range to expanded UTC date strings (yyyy-MM-dd).
 * Used for daily-stats endpoints that filter on a Date column bucketed by UTC.
 * The local start/end-of-day may span two UTC dates, so we take the date
 * component of each converted boundary.
 */
export function toExpandedUTCDateRange(
  dateRange: DateRange | undefined,
): { from_date?: string; to_date?: string } {
  if (!dateRange) return {};
  const from_date = dateRange.from
    ? format(new Date(localStartOfDayUTC(dateRange.from)), "yyyy-MM-dd")
    : undefined;
  const to_date = dateRange.to
    ? format(new Date(localEndOfDayUTC(dateRange.to)), "yyyy-MM-dd")
    : undefined;
  return { from_date, to_date };
}

export function toMetricsApiParams(
  dateRange: DateRange | undefined,
  agentId?: string,
): MetricsApiParams {
  return {
    from_date: dateRange?.from ? localStartOfDayUTC(dateRange.from) : undefined,
    to_date: dateRange?.to ? localEndOfDayUTC(dateRange.to) : undefined,
    agent_id: agentId && agentId !== "all" ? agentId : undefined,
  };
}

export function buildQueryString(params?: MetricsApiParams): string {
  const searchParams = new URLSearchParams();
  if (params?.from_date) searchParams.set("from_date", params.from_date);
  if (params?.to_date) searchParams.set("to_date", params.to_date);
  if (params?.agent_id) searchParams.set("agent_id", params.agent_id);
  if (params?.compare) searchParams.set("compare", params.compare);
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}
