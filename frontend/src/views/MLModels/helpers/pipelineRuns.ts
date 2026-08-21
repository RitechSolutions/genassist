import { PipelineRun } from "@/interfaces/ml-model-pipeline.interface";

export type PipelineRunStatus = PipelineRun["status"];

/** Statuses that are still moving, so the detail page keeps polling for them. */
const ACTIVE_STATUSES = new Set<string>(["pending", "running"]);

export function isRunActive(status: string | null | undefined): boolean {
  return !!status && ACTIVE_STATUSES.has(status);
}

export function hasActiveRun(runs: PipelineRun[]): boolean {
  return runs.some((run) => isRunActive(run.status));
}

export interface RunStatusMeta {
  label: string;
  /** Tailwind classes for the badge, mirroring the status colors used elsewhere. */
  className: string;
  spinning: boolean;
}

const STATUS_META: Record<string, RunStatusMeta> = {
  completed: {
    label: "Completed",
    className:
      "border-transparent bg-green-100 text-green-800 dark:bg-green-500/20 dark:text-green-400",
    spinning: false,
  },
  running: {
    label: "Running",
    className:
      "border-transparent bg-blue-100 text-blue-800 dark:bg-blue-500/20 dark:text-blue-400",
    spinning: true,
  },
  pending: {
    label: "Pending",
    className:
      "border-transparent bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-400",
    spinning: true,
  },
  failed: {
    label: "Failed",
    className:
      "border-transparent bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-400",
    spinning: false,
  },
  cancelled: {
    label: "Cancelled",
    className: "border-border bg-muted text-muted-foreground",
    spinning: false,
  },
};

export function runStatusMeta(status: string): RunStatusMeta {
  return (
    STATUS_META[status] ?? {
      label: status,
      className: "border-border bg-muted text-muted-foreground",
      spinning: false,
    }
  );
}

/**
 * Elapsed time between two timestamps as a compact "1h 4m" / "3m 12s" / "8s"
 * label. The previous implementation rounded to whole minutes, so every run
 * under 30 seconds read as "0 min".
 */
export function formatRunDuration(
  startedAt: string | null | undefined,
  completedAt: string | null | undefined
): string | null {
  if (!startedAt || !completedAt) return null;
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;

  const totalSeconds = Math.round((end - start) / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

/** Compact byte size for artifact rows (e.g. "1.4 MB"). */
export function formatFileSize(bytes: number | null | undefined): string | null {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return null;
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

/**
 * A standard 5-field cron expression. Empty is treated as valid — it means
 * "manual runs only".
 */
export function isValidCron(cron: string): boolean {
  if (!cron.trim()) return true;
  const field = String.raw`((\*|\d+)(-\d+)?)(\/\d+)?(,((\*|\d+)(-\d+)?)(\/\d+)?)*`;
  return new RegExp(`^${field}(\\s+${field}){4}$`).test(cron.trim());
}

/** Value used by the "custom cron" option in the schedule picker. */
export const CUSTOM_CRON = "custom";

/**
 * The schedules people actually pick, so configuring a nightly retrain does not
 * require knowing cron syntax. An empty expression means "manual runs only".
 */
export const CRON_PRESETS: ReadonlyArray<{
  value: string;
  label: string;
  hint: string;
}> = [
  { value: "", label: "Manual only", hint: "Run this pipeline on demand" },
  { value: "0 * * * *", label: "Hourly", hint: "At the top of every hour" },
  { value: "0 0 * * *", label: "Daily", hint: "Every day at 00:00" },
  { value: "0 0 * * 1", label: "Weekly", hint: "Every Monday at 00:00" },
  { value: "0 0 1 * *", label: "Monthly", hint: "On the 1st at 00:00" },
];

const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

const pad = (value: number): string => String(value).padStart(2, "0");
const isWildcard = (field: string): boolean => field === "*";
const asNumber = (field: string): number | null =>
  /^\d+$/.test(field) ? Number(field) : null;
const asStep = (field: string): number | null => {
  const match = /^\*\/(\d+)$/.exec(field);
  return match ? Number(match[1]) : null;
};

/**
 * Plain-English summary of the common cron shapes, so the picker can confirm
 * what a custom expression actually does. Returns null for expressions that are
 * invalid or too complex to describe (callers show a generic label instead).
 */
export function describeCron(cron: string): string | null {
  const trimmed = cron.trim();
  if (!trimmed || !isValidCron(trimmed)) return null;

  const [minute, hour, dayOfMonth, month, dayOfWeek] = trimmed.split(/\s+/);
  if (!isWildcard(month)) return null;

  const minuteStep = asStep(minute);
  if (
    minuteStep &&
    isWildcard(hour) &&
    isWildcard(dayOfMonth) &&
    isWildcard(dayOfWeek)
  ) {
    return `Every ${minuteStep} minutes`;
  }

  const minuteValue = asNumber(minute);
  if (minuteValue === null) return null;

  const hourStep = asStep(hour);
  if (hourStep && isWildcard(dayOfMonth) && isWildcard(dayOfWeek)) {
    return `Every ${hourStep} hours at :${pad(minuteValue)}`;
  }

  if (isWildcard(hour)) {
    return isWildcard(dayOfMonth) && isWildcard(dayOfWeek)
      ? `Every hour at :${pad(minuteValue)}`
      : null;
  }

  const hourValue = asNumber(hour);
  if (hourValue === null) return null;
  const time = `${pad(hourValue)}:${pad(minuteValue)}`;

  const weekday = asNumber(dayOfWeek);
  if (weekday !== null && isWildcard(dayOfMonth)) {
    return `Every ${WEEKDAYS[weekday % 7]} at ${time}`;
  }

  const monthDay = asNumber(dayOfMonth);
  if (monthDay !== null && isWildcard(dayOfWeek)) {
    return `Monthly on day ${monthDay} at ${time}`;
  }

  if (isWildcard(dayOfMonth) && isWildcard(dayOfWeek)) {
    return `Every day at ${time}`;
  }
  return null;
}

/**
 * The model file a run produced, read out of the workflow's final output.
 * Promotion copies this onto the model (see the backend's `promote_run`).
 */
export function runModelFilePath(run: PipelineRun): string | null {
  const output = (run.execution_output as { output?: unknown } | undefined)?.output;
  if (!output || typeof output !== "object") return null;
  const path = (output as { model_file_path?: unknown }).model_file_path;
  return typeof path === "string" && path.length > 0 ? path : null;
}

/**
 * Whether this run's output is the model's currently active file. There is no
 * "promoted" column on a run, so it is derived by matching the file the run
 * produced against the one the model now points at.
 */
export function isRunPromoted(
  run: PipelineRun,
  modelFilePath: string | null | undefined
): boolean {
  const produced = runModelFilePath(run);
  return !!produced && !!modelFilePath && produced === modelFilePath;
}

/** Whether this run used the pipeline configuration that is the model's default. */
export function isRunDefaultPipeline(
  run: PipelineRun,
  defaultConfigId: string | null | undefined
): boolean {
  return !!defaultConfigId && run.pipeline_config_id === defaultConfigId;
}

/**
 * Whether promoting this run would still change anything. Promotion always makes
 * the run's pipeline the model's default, and additionally points the model at
 * the run's model file when it produced one — so a run that produced no file is
 * fully promoted as soon as its pipeline is the default.
 */
export function isRunFullyPromoted(
  run: PipelineRun,
  modelFilePath: string | null | undefined,
  defaultConfigId: string | null | undefined
): boolean {
  const isDefault = isRunDefaultPipeline(run, defaultConfigId);
  if (!isDefault) return false;
  return runModelFilePath(run) ? isRunPromoted(run, modelFilePath) : true;
}
