import { apiRequest } from "@/config/api";
import type { TopicsReportResponse } from "@/interfaces/analytics.interface";
import { buildQueryString, type MetricsApiParams } from "@/helpers/analyticsParams";

export type FetchedMetricsData = {
  "Customer Satisfaction": string;
  "Resolution Rate": string;
  "Positive Sentiment": string;
  "Negative Sentiment": string;
  "Efficiency": string;
  "Response Time": string;
  "Quality of Service": string;
  "total_analyzed_audios": number;
};

export const fetchMetrics = async (params?: MetricsApiParams): Promise<FetchedMetricsData | null> => {
  return await apiRequest<FetchedMetricsData>("get", `/analytics/metrics${buildQueryString(params)}`);
};

export type DailyMetricsItem = {
  date: string;
  satisfaction: number;
  quality_of_service: number;
  resolution_rate: number;
};

export const fetchMetricsDaily = async (params?: MetricsApiParams): Promise<DailyMetricsItem[]> => {
  const res = await apiRequest<{ items: DailyMetricsItem[] }>("get", `/analytics/metrics/daily${buildQueryString(params)}`);
  return res?.items ?? [];
};

export const fetchTopicsReport = async (): Promise<TopicsReportResponse | null> => {
  return await apiRequest<TopicsReportResponse>("get", "/topics-report");
};
