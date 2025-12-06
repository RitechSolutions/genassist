export type JobProgress = {
  status?: string;
  is_running?: boolean;
  message?: string;
  progress_percentage?: number;
  accuracy?: number;
  estimated_seconds_remaining?: number;
};

export type UsageMetrics = {
  total_interactions?: unknown;
  total_tokens?: unknown;
};

export type AccuracyPoint = { label: string; value: number };

export type FineTuneJobsCardProps = {
  searchQuery: string;
  refreshKey?: number;
};