import React, { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/dialog";
import { getRunTurnTrace } from "@/services/testSuites";
import { getWorkflowById } from "@/services/workflows";
import NodeExecutionView from "@/views/AIAgents/Workflows/components/execution/NodeExecutionView";
import { buildExecutionViewModel } from "@/views/AIAgents/Workflows/utils/executionView";

interface TurnStepsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  runId: string;
  caseId: string;
  /** The version the run used, whose graph the steps are drawn on. */
  workflowId: string;
  runCreatedAt?: string;
  title: string;
  description?: string;
}

/** The steps one turn took, drawn on the workflow like the editor's test runs. */
export const TurnStepsDialog: React.FC<TurnStepsDialogProps> = ({
  open,
  onOpenChange,
  runId,
  caseId,
  workflowId,
  runCreatedAt,
  title,
  description = "The steps this turn took. Select a step to see what went in and what came out.",
}) => {
  const trace = useQuery({
    queryKey: ["run-turn-trace", runId, caseId],
    queryFn: () => getRunTurnTrace(runId, caseId),
    enabled: open,
    staleTime: Infinity,
  });
  const workflow = useQuery({
    queryKey: ["evaluation-run-workflow", workflowId],
    queryFn: () => getWorkflowById(workflowId),
    enabled: open && Boolean(workflowId),
    staleTime: 60_000,
    retry: false,
  });

  const response = trace.data?.execution_trace ?? null;
  const graph = workflow.data ?? null;
  const steps = useMemo(() => (response ? buildExecutionViewModel(response, graph).totalNodes : 0), [response, graph]);
  // Saving in the editor changes a version in place, so the graph can differ from what ran.
  const editedSince =
    graph?.updated_at && runCreatedAt && new Date(graph.updated_at).getTime() > new Date(runCreatedAt).getTime();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[95vh] w-[95vw] max-w-6xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {editedSince && (
          <p className="text-xs text-muted-foreground">
            This version was edited after the run, so the diagram may not match it exactly.
          </p>
        )}
        {trace.isLoading || workflow.isLoading ? (
          <div role="status" className="flex h-60 items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            <span className="sr-only">Loading the steps</span>
          </div>
        ) : trace.isError || !trace.data ? (
          <p className="py-10 text-center text-sm text-destructive">The steps could not be loaded.</p>
        ) : !response || !steps ? (
          <p className="py-10 text-center text-sm text-muted-foreground">This turn has no recorded steps.</p>
        ) : (
          <NodeExecutionView response={response} testing={false} error={null} workflow={graph} />
        )}
      </DialogContent>
    </Dialog>
  );
};
