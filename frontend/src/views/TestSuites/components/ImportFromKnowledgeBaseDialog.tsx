import React from "react";
import { Button } from "@/components/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import type { QuestionRunStatus, TestSuite } from "@/interfaces/testSuite.interface";
import { type RunNote, isRunInProgress } from "../helpers/questionRun";
import { useQuestionRunDialog } from "../hooks/useQuestionRunDialog";
import { QuestionRunProgress } from "./QuestionRunProgress";
import { QuestionRunSetup } from "./QuestionRunSetup";

interface ImportFromKnowledgeBaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  suite: TestSuite | null;
  /** The dataset's run in progress, else its last run's outcome. */
  run: QuestionRunStatus;
  /** Set while the run's latest status cannot be read. */
  statusProblem: RunNote | null;
  onStarted: (run: QuestionRunStatus) => void;
}

interface RunViewProps {
  run: QuestionRunStatus;
  statusProblem: RunNote | null;
  knowledgeBaseName: string | null;
  /** True when Start found a run already holding the dataset, so nothing new was started. */
  wasAlreadyRunning: boolean;
}

const RunView: React.FC<RunViewProps> = ({ run, statusProblem, knowledgeBaseName, wasAlreadyRunning }) => (
  <div className="space-y-3">
    {wasAlreadyRunning && (
      <p className="text-sm text-destructive">
        A run was already in progress on this dataset, so a new one was not started.
      </p>
    )}
    {knowledgeBaseName && (
      <p className="text-sm text-muted-foreground">Knowledge base: {knowledgeBaseName}</p>
    )}
    <QuestionRunProgress run={run} statusProblem={statusProblem} />
    {isRunInProgress(run) && (
      <p className="text-xs text-muted-foreground">
        You can close this window. The run continues in the background.
      </p>
    )}
  </div>
);

export const ImportFromKnowledgeBaseDialog: React.FC<ImportFromKnowledgeBaseDialogProps> = ({
  open,
  onOpenChange,
  suite,
  run,
  statusProblem,
  onStarted,
}) => {
  const dialog = useQuestionRunDialog({ open, suite, run, onStarted });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] p-0 overflow-hidden flex flex-col max-h-[80vh]">
        <DialogHeader className="p-6 pb-4 shrink-0">
          <DialogTitle>Write questions from a knowledge base into "{suite?.name}"</DialogTitle>
          <DialogDescription>
            A model reads each article and writes two customer-style questions. Each one is added
            as a one-turn conversation that names the article the search should find. Questions
            that copy the article, or that another article answers better, are left out.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 pb-4 space-y-4">
          {dialog.showsRun ? (
            <RunView
              run={run}
              statusProblem={statusProblem}
              knowledgeBaseName={dialog.knowledgeBaseName}
              wasAlreadyRunning={dialog.wasAlreadyRunning}
            />
          ) : (
            <>
              {dialog.lastOutcome && (
                <p className="text-xs text-muted-foreground">Last run: {dialog.lastOutcome.text}</p>
              )}
              <QuestionRunSetup
                form={dialog.form}
                onChange={dialog.changeForm}
                knowledgeBases={dialog.knowledgeBases}
                providers={dialog.providers}
                isSampleInvalid={dialog.count.isSampleInvalid}
                note={dialog.count.note}
                onRecount={dialog.count.hasFailed ? dialog.count.recount : undefined}
              />
            </>
          )}
        </div>

        {/* sm:justify-between is required: DialogFooter ships sm:justify-end. */}
        <DialogFooter className="border-t px-6 py-3 shrink-0 flex items-center justify-between gap-3 sm:justify-between">
          <span className="text-xs text-destructive">{dialog.showsRun ? "" : dialog.startError}</span>
          {dialog.showsRun ? (
            <Button size="sm" variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          ) : (
            <Button size="sm" disabled={!dialog.canStart} loading={dialog.isStarting} onClick={dialog.start}>
              Start
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ImportFromKnowledgeBaseDialog;
