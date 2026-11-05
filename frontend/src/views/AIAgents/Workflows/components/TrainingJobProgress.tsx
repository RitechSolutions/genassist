import { Progress } from "@/components/progress";
import { TrainingJob } from "@/services/workflows";

const formatElapsed =(seconds = 0): string => {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}m ${rest.toString().padStart(2, "0")}s` : `${rest}s`;
};

interface TrainingJobProgressProps {
  job: TrainingJob;
}

/** Progress of a test run that trains a model on the background ML worker. */
export const TrainingJobProgress = ({ job }: TrainingJobProgressProps) => {
  const { message, percent, elapsed_seconds } = job.progress;
  return (
    <div className="w-full space-y-2 text-sm" data-testid="training-job-progress">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">
          {job.status === "queued" ? "Queued on the training worker" : "Training on the background worker"}
        </span>
        <span className="tabular-nums text-muted-foreground">{formatElapsed(elapsed_seconds)}</span>
      </div>
      <Progress value={percent} className="h-2" />
      <p className="text-muted-foreground">{message}</p>
    </div>
  );
};
