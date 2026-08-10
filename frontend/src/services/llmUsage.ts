import { apiRequest } from "@/config/api";
import type {
  LlmUsageBreakdownResponse,
  LlmUsageDimension,
  LlmUsageFilterOptionsResponse,
  LlmUsageQueryFilters,
  LlmUsageSummaryResponse,
  LlmUsageTimeseriesResponse,
} from "@/interfaces/llmUsage.interface";

const BASE = "/analytics/llm-usage";

function buildQueryString(params: Record<string, string | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v as string)}`);
  return parts.length > 0 ? `?${parts.join("&")}` : "";
}

// Fetchers propagate failures so callers can show an error instead of an empty report
export const fetchLlmUsageSummary = (params?: LlmUsageQueryFilters): Promise<LlmUsageSummaryResponse> =>
  apiRequest<LlmUsageSummaryResponse>("get", `${BASE}/summary${buildQueryString({ ...params })}`);

export const fetchLlmUsageBreakdown = (
  dimension: LlmUsageDimension,
  params?: LlmUsageQueryFilters
): Promise<LlmUsageBreakdownResponse> =>
  apiRequest<LlmUsageBreakdownResponse>("get", `${BASE}/breakdown${buildQueryString({ dimension, ...params })}`);

export const fetchLlmUsageTimeseries = (params?: LlmUsageQueryFilters): Promise<LlmUsageTimeseriesResponse> =>
  apiRequest<LlmUsageTimeseriesResponse>("get", `${BASE}/timeseries${buildQueryString({ ...params })}`);

export const fetchLlmUsageFilterOptions = (
  params?: LlmUsageQueryFilters
): Promise<LlmUsageFilterOptionsResponse> =>
  apiRequest<LlmUsageFilterOptionsResponse>("get", `${BASE}/filter-options${buildQueryString({ ...params })}`);
