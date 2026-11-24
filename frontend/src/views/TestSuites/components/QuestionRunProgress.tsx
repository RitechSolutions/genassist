import React from "react";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/button";
import { Progress } from "@/components/progress";
import type { QuestionRunStatus } from "@/interfaces/testSuite.interface";
import {
  type RunNote,
  describeOutcome,
  describeProgress,
  progressPercent,
} from "../helpers/questionRun";

interface QuestionRunProgressProps {
  run: QuestionRunStatus;
  /** Set while the run's latest status cannot be read. */
  statusProblem?: RunNote | null;
}

export const RunNoteLine: React.FC<{ note: RunNote }> = ({ note }) => {
  const Icon = note.isProblem ? AlertCircle : CheckCircle2;
  const tone = note.isProblem ? "text-destructive" : "text-emerald-600";
  return (
    <div className="flex items-start gap-2 text-sm">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone}`} />
      <span>{note.text}</span>
    </div>
  );
};

/** A run's progress while it is in progress, and how it ended once it has. */
export const QuestionRunProgress: React.FC<QuestionRunProgressProps> = ({ run, statusProblem }) => {
  const outcome = describeOutcome(run);
  if (outcome) return <RunNoteLine note={outcome} />;
  if (statusProblem) return <RunNoteLine note={statusProblem} />;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm">
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
        <span>{describeProgress(run)}</span>
      </div>
      <Progress value={progressPercent(run)} className="h-2" />
    </div>
  );
};

/** The line the dataset page shows while questions are being written. */
export const QuestionRunNotice: React.FC<QuestionRunProgressProps & { onOpen: () => void }> = ({
  run,
  statusProblem,
  onOpen,
}) => (
  <div className="flex flex-col gap-3 rounded-lg border bg-card px-6 py-4 dark:bg-zinc-900 sm:flex-row sm:items-center">
    <div className="min-w-0 flex-1 space-y-1">
      <div className="text-sm font-medium">Writing questions from a knowledge base</div>
      <QuestionRunProgress run={run} statusProblem={statusProblem} />
    </div>
    <Button variant="outline" size="sm" className="shrink-0" onClick={onOpen}>
      Details
    </Button>
  </div>
);
