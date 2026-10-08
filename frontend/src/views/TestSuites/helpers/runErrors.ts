import { extractErrorMessage } from "@/helpers/apiError";

const statusOf = (err: unknown): number | undefined =>
  (err as { response?: { status?: number } } | null)?.response?.status;

const errorKeyOf = (err: unknown): string | null => {
  const data = (err as { response?: { data?: { error_key?: unknown } } } | null)?.response?.data;
  return typeof data?.error_key === "string" ? data.error_key : null;
};

// A 409 means the evaluation already has a run queued or running.
export const isRunConflict = (err: unknown): boolean => statusOf(err) === 409;

// What to tell the user when the backend refuses to start a run.
export const runStartErrorMessage = (err: unknown): string => {
  if (isRunConflict(err)) return "This evaluation is already running.";
  switch (errorKeyOf(err)) {
    case "evaluation_target_not_a_version":
      return "That version does not belong to this workflow.";
    case "evaluation_workflow_required":
      return "This evaluation has no workflow. Edit it and choose one.";
    default:
      return extractErrorMessage(err, "Couldn't start the run.");
  }
};
