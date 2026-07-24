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

export const fetchLlmUsageSummary = async (
  params?: LlmUsageQueryFilters
): Promise<LlmUsageSummaryResponse | null> => {
  try {
    return await apiRequest<LlmUsageSummaryResponse>("get", `${BASE}/summary${buildQueryString({ ...params })}`);
  } catch (error) {
    console.error("Error fetching LLM usage summary:", error);
    return null;
  }
};

export const fetchLlmUsageBreakdown = async (
  dimension: LlmUsageDimension,
  params?: LlmUsageQueryFilters
): Promise<LlmUsageBreakdownResponse | null> => {
  try {
    return await apiRequest<LlmUsageBreakdownResponse>(
      "get",
      `${BASE}/breakdown${buildQueryString({ dimension, ...params })}`
    );
  } catch (error) {
    console.error("Error fetching LLM usage breakdown:", error);
    return null;
  }
};

export const fetchLlmUsageTimeseries = async (
  params?: LlmUsageQueryFilters
): Promise<LlmUsageTimeseriesResponse | null> => {
  try {
    return await apiRequest<LlmUsageTimeseriesResponse>("get", `${BASE}/timeseries${buildQueryString({ ...params })}`);
  } catch (error) {
    console.error("Error fetching LLM usage timeseries:", error);
    return null;
  }
};

export const fetchLlmUsageFilterOptions = async (
  params?: LlmUsageQueryFilters
): Promise<LlmUsageFilterOptionsResponse | null> => {
  try {
    return await apiRequest<LlmUsageFilterOptionsResponse>(
      "get",
      `${BASE}/filter-options${buildQueryString({ ...params })}`
    );
  } catch (error) {
    console.error("Error fetching LLM usage filter options:", error);
    return null;
  }
};
