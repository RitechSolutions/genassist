import { apiRequest } from "@/config/api";
import type { TopicsReportResponse } from "@/interfaces/analytics.interface";

export type FetchedMetricsData = {
  "Customer Satisfaction": string;
  "Resolution Rate": string;
  "Positive Sentiment": string;
  "Neutral Sentiment": string;
  "Negative Sentiment": string;
  "Efficiency": string;
  "Response Time": string;
  "Quality of Service": string;
  "total_analyzed_audios": number;
};

export const fetchMetrics = async (): Promise<FetchedMetricsData | null> => {
  return await apiRequest<FetchedMetricsData>("get", "/audio/metrics/");
};

export const fetchTopicsReport = async (): Promise<TopicsReportResponse | null> => {
  return await apiRequest<TopicsReportResponse>("get", "/topics-report");
};
