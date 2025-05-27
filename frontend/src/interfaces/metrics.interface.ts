export interface MetricsData {
  metrics: Array<{
    "Customer Satisfaction": string;
    "Efficiency": string;
    "Quality of Service": string;
    "Resolution Rate": string;
    "Response Time": string;
  }>;
  total_analyzed_audios: number;
}
