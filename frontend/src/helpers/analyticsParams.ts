import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import { utcDayEnd, utcDayStart } from "@/helpers/dateRange";

export type MetricsApiParams = {
  from_date?: string;
  to_date?: string;
  agent_id?: string;
  group_id?: string;
  compare?: string;
};

/**
 * Legacy date-string params (yyyy-MM-dd) for the menus that still send day filters.
 */
export function toExpandedUTCDateRange(
  dateRange: DateRange | undefined,
): { from_date?: string; to_date?: string } {
  if (!dateRange) return {};
  return {
    from_date: dateRange.from ? format(dateRange.from, "yyyy-MM-dd") : undefined,
    to_date: dateRange.to ? format(dateRange.to, "yyyy-MM-dd") : undefined,
  };
}

export function toMetricsApiParams(
  dateRange: DateRange | undefined,
  agentId?: string,
  groupId?: string,
): MetricsApiParams {
  const agent_id = agentId && agentId !== "all" ? agentId : undefined;
  const group_id =
    groupId && groupId !== "all" && !agent_id ? groupId : undefined;
  return {
    from_date: dateRange?.from ? utcDayStart(dateRange.from) : undefined,
    to_date: dateRange?.to ? utcDayEnd(dateRange.to) : undefined,
    agent_id,
    group_id,
  };
}

export function buildQueryString(params?: MetricsApiParams): string {
  const searchParams = new URLSearchParams();
  if (params?.from_date) searchParams.set("from_date", params.from_date);
  if (params?.to_date) searchParams.set("to_date", params.to_date);
  if (params?.agent_id) searchParams.set("agent_id", params.agent_id);
  if (params?.group_id) searchParams.set("group_id", params.group_id);
  if (params?.compare) searchParams.set("compare", params.compare);
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}
