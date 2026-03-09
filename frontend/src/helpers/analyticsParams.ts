import { format } from "date-fns";
import type { DateRange } from "react-day-picker";

export type MetricsApiParams = {
  from_date?: string;
  to_date?: string;
  agent_id?: string;
};

export function toMetricsApiParams(
  dateRange: DateRange | undefined,
  agentId?: string,
): MetricsApiParams {
  return {
    from_date: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd'T'HH:mm:ss") : undefined,
    to_date: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd'T'23:59:59") : undefined,
    agent_id: agentId && agentId !== "all" ? agentId : undefined,
  };
}

export function buildQueryString(params?: MetricsApiParams): string {
  const searchParams = new URLSearchParams();
  if (params?.from_date) searchParams.set("from_date", params.from_date);
  if (params?.to_date) searchParams.set("to_date", params.to_date);
  if (params?.agent_id) searchParams.set("agent_id", params.agent_id);
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}
