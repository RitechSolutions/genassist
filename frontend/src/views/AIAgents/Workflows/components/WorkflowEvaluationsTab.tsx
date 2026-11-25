import React, { useState } from "react";
import { ClipboardCheck, Lock } from "lucide-react";

import { usePermissions } from "@/context/PermissionContext";
import { WorkflowEvaluationsPanel } from "@/views/TestSuites/components/WorkflowEvaluationsPanel";
import { EvaluationDetailPanel } from "@/views/TestSuites/components/EvaluationDetailPanel";
import { EvaluationEditorView } from "@/views/TestSuites/components/EvaluationEditorView";

// The evaluations API is gated on this permission (the builder itself only needs
// read:llm_analyst), so a user who can edit workflows may still lack eval access.
const EVALUATION_PERMISSION = "test:workflow";

type TabView =
  | { kind: "list" }
  | { kind: "detail"; id: string }
  // The editor returns to where it was opened from.
  | { kind: "edit"; id: string | null; back: { kind: "list" } | { kind: "detail"; id: string } };

interface WorkflowEvaluationsTabProps {
  /** Active workflow id (agent.workflow_id). Undefined while the agent loads or for an unsaved workflow. */
  workflowId?: string;
  /** The saved version open in the builder, which runs from this tab preselect. */
  openWorkflowId?: string;
}

const CenteredState: React.FC<{
  icon: React.ReactNode;
  title: string;
  description?: string;
}> = ({ icon, title, description }) => (
  <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
    <div className="rounded-full bg-muted p-4 text-muted-foreground">{icon}</div>
    <div>
      <p className="text-sm font-medium">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
    </div>
  </div>
);

/**
 * Evaluations tab content for the workflow builder. Reuses the shared TestSuites
 * panels: it shows this workflow's evaluations (create pinned to the workflow) and
 * swaps to an in-tab detail view or editor — so the whole evaluations flow
 * stays inside the builder without navigating away.
 */
const WorkflowEvaluationsTab: React.FC<WorkflowEvaluationsTabProps> = ({ workflowId, openWorkflowId }) => {
  const permissions = usePermissions();
  const canEvaluate =
    permissions.includes("*") || permissions.includes(EVALUATION_PERMISSION);
  const [view, setView] = useState<TabView>({ kind: "list" });

  if (!canEvaluate) {
    return (
      <CenteredState
        icon={<Lock className="h-8 w-8" />}
        title="No access to evaluations"
        description="You don't have permission to view or run evaluations for this workflow."
      />
    );
  }

  if (!workflowId) {
    return (
      <CenteredState
        icon={<ClipboardCheck className="h-8 w-8" />}
        title="Save the workflow to add evaluations"
        description="Once this workflow is saved, its evaluations will show up here."
      />
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* space-y-6 mirrors PageLayout (the standalone pages' wrapper) so both panels
          space identically; pt-16 clears the floating tab switcher at the top-left. */}
      <div className="mx-auto w-full max-w-7xl space-y-6 px-4 pb-4 pt-16 sm:px-6 sm:pb-6">
        {view.kind === "edit" ? (
          <EvaluationEditorView
            evaluationId={view.id ?? undefined}
            lockedWorkflowId={view.id ? undefined : workflowId}
            runVersionId={openWorkflowId}
            onCancel={() => setView(view.back)}
            // An edit returns where it began, as on the evaluations page; a new evaluation opens.
            onDone={(id) => setView(view.id ? view.back : { kind: "detail", id })}
          />
        ) : view.kind === "detail" ? (
          <EvaluationDetailPanel
            key={view.id}
            evaluationId={view.id}
            onBack={() => setView({ kind: "list" })}
            backLabel="Back to evaluations"
            embedded
            runVersionId={openWorkflowId}
            onEditEvaluation={(id) => setView({ kind: "edit", id, back: { kind: "detail", id } })}
          />
        ) : (
          <WorkflowEvaluationsPanel
            workflowId={workflowId}
            runVersionId={openWorkflowId}
            allowCreate
            onOpenEvaluation={(id) => setView({ kind: "detail", id })}
            onCreateEvaluation={() => setView({ kind: "edit", id: null, back: { kind: "list" } })}
            onEditEvaluation={(id) => setView({ kind: "edit", id, back: { kind: "list" } })}
          />
        )}
      </div>
    </div>
  );
};

export default WorkflowEvaluationsTab;
