import type { FineTuneJob } from "@/interfaces/fineTune.interface";
import type { AccuracyPoint } from "@/views/FineTune/types";

export const inProgressStatuses = new Set(["running", "queued", "validating_files"]);

export const formatStatusLabel = (status: string) => {
  if (!status) return "Unknown";
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

export const normalizePercent = (value: unknown): number | null => {
  if (value === undefined || value === null) return null;
  const num = Number(value);
  if (!isFinite(num)) return null;
  const scaled = num <= 1 ? num * 100 : num;
  return Math.round(scaled);
};

export const normalizeNumber = (value: unknown): number | null => {
  if (value === undefined || value === null) return null;
  const num = Number(value);
  return isFinite(num) ? num : null;
};

export const normalizeSeconds = (value: unknown): number | null => {
  if (value === undefined || value === null) return null;
  const num = Number(value);
  if (!isFinite(num) || num < 0) return null;
  return Math.round(num);
};

export const formatNumber = (value: unknown): string => {
  if (value === undefined || value === null || isNaN(Number(value))) return "—";
  return new Intl.NumberFormat().format(Number(value));
};

const toDate = (value: unknown): Date | null => {
  if (!value) return null;
  if (value instanceof Date) return value;
  const num = Number(value);
  if (!isNaN(num)) {
    const isSeconds = num < 1e12;
    return new Date(isSeconds ? num * 1000 : num);
  }
  const parsed = new Date(String(value));
  return isNaN(parsed.getTime()) ? null : parsed;
};

export const formatDate = (value: unknown): string => {
  const date = toDate(value);
  if (!date) return "—";
  return date.toLocaleString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
  });
};

export const getAccuracyFromEvents = (job: FineTuneJob, isRunning: boolean): number | null => {
  const events = (job as Record<string, unknown>).events as
    | Array<{ metrics?: Record<string, unknown> }>
    | undefined;
  if (!Array.isArray(events) || !events.length) return null;

  const lastWithMetrics = [...events]
    .reverse()
    .find((e) => e.metrics && Object.keys(e.metrics || {}).length > 0);

  if (!lastWithMetrics?.metrics) return null;
  const metrics = lastWithMetrics.metrics;
  const accuracyFields = isRunning
    ? [
        "valid_mean_token_accuracy",
        "train_mean_token_accuracy",
        "full_valid_mean_token_accuracy",
        "full_valid_loss",
      ]
    : [
        "full_valid_mean_token_accuracy",
        "valid_mean_token_accuracy",
        "train_mean_token_accuracy",
        "full_valid_loss",
      ];

  for (const key of accuracyFields) {
    const v = metrics[key as keyof typeof metrics];
    const num = Number(v);
    if (!isNaN(num)) {
      if (key.includes("loss")) {
        return Math.max(0, Math.min(100, Math.round((1 - num) * 100)));
      }
      return Math.round(num * (num <= 1 ? 100 : 1));
    }
  }

  return null;
};

export const buildAccuracySeries = (
  events: Array<{ metrics?: Record<string, unknown> }> | undefined
): AccuracyPoint[] => {
  if (!Array.isArray(events) || !events.length) return [];
  let counter = 0;

  return events.reduce<AccuracyPoint[]>((acc, e) => {
    const val =
      Number(e.metrics?.full_valid_mean_token_accuracy) ||
      Number(e.metrics?.valid_mean_token_accuracy) ||
      Number(e.metrics?.train_mean_token_accuracy);
    if (isNaN(val)) return acc;

    counter += 1;
    const percent = Math.round(val * (val <= 1 ? 100 : 1));
    const stepNumber =
      Number.isFinite(e.metrics?.step) && Number(e.metrics?.step) > 0
        ? Number(e.metrics?.step)
        : counter;

    acc.push({
      label: `Step ${stepNumber}`,
      value: percent,
    });
    return acc;
  }, []);
};