import type { Dispatch, SetStateAction } from "react";
import type { FineTuneJob } from "@/interfaces/fineTune.interface";

export type JobProgress = {
  job_id?: string;
  status?: string;
  is_running?: boolean;
  message?: string;
  progress_percentage?: number;
  accuracy?: number;
  estimated_seconds_remaining?: number;
  latest_metrics?: Record<string, unknown>;
};

export type UsageMetrics = {
  total_interactions?: unknown;
  total_tokens?: unknown;
};

export type AccuracyPoint = { label: string; value: number };

export type FineTuneJobsCardProps = {
  searchQuery: string;
  jobs: FineTuneJob[];
  setJobs: Dispatch<SetStateAction<FineTuneJob[]>>;
  loading: boolean;
  error: string | null;
  onNewFineTuneJob?: () => void;
};