import { useState } from "react";
import { Button } from "@/components/button";
import { Progress } from "@/components/progress";
import { cancelTrainingJob, TrainingJob } from "@/services/workflows";

const formatElapsed = (seconds = 0): string => {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}m ${rest.toString().padStart(2, "0")}s` : `${rest}s`;
};

interface TrainingJobProgressProps {
  job: TrainingJob;
}

/** Progress of a test run that trains a model on the background ML worker, with a way to cancel it. */
export const TrainingJobProgress = ({ job }: TrainingJobProgressProps) => {
  const { message, percent, elapsed_seconds } = job.progress;
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  // The test that is waiting on the job sees the cancelled status on its next poll.
  const handleCancel = async () => {
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelTrainingJob(job.job_id);
    } catch {
      setCancelError("Could not cancel the training test. Try again.");
      setCancelling(false);
    }
  };

  return (
    <div className="w-full space-y-2 text-sm" data-testid="training-job-progress">
      {job.reattached && (
        <p className="text-muted-foreground" data-testid="training-job-reattached">
          You already had a training test running, so this shows that one. Cancel it to run a new test.
        </p>
      )}
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">
          {job.status === "queued" ? "Queued on the training worker" : "Training on the background worker"}
        </span>
        <span className="tabular-nums text-muted-foreground">{formatElapsed(elapsed_seconds)}</span>
      </div>
      <Progress value={percent} className="h-2" />
      <div className="flex items-center justify-between gap-2">
        <p className="text-muted-foreground">{cancelling ? "Cancelling..." : message}</p>
        <Button variant="outline" size="sm" onClick={handleCancel} disabled={cancelling}>
          Cancel training
        </Button>
      </div>
      {cancelError && <p className="text-destructive">{cancelError}</p>}
    </div>
  );
};
