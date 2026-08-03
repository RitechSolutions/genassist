import type { BedrockFineTuneJob } from "@/interfaces/bedrockFineTune.interface";

/** Job statuses that indicate the job is still running / not yet terminal. */
export const bedrockInProgressStatuses = new Set(["inprogress", "stopping"]);

/** Job statuses that indicate the job has finished (successfully or not). */
export const bedrockTerminalStatuses = new Set(["completed", "failed", "stopped"]);

/** Deployment statuses that indicate a deployment exists or is being created. */
export const bedrockActiveDeploymentStatuses = new Set(["active", "creating"]);

/** Turn a PascalCase status ("InProgress") into a spaced label ("In Progress"). */
export const formatBedrockStatusLabel = (status: string): string => {
  if (!status) return "Unknown";
  return status
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

export const isBedrockJobInProgress = (job: BedrockFineTuneJob): boolean =>
  bedrockInProgressStatuses.has(String(job.status || "").toLowerCase());

export const isBedrockJobCompleted = (job: BedrockFineTuneJob): boolean =>
  String(job.status || "").toLowerCase() === "completed";
