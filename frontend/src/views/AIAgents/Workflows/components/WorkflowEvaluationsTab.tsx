import React, { useState } from "react";
import { ClipboardCheck, Lock } from "lucide-react";

import { usePermissions } from "@/context/PermissionContext";
import { WorkflowEvaluationsPanel } from "@/views/TestSuites/components/WorkflowEvaluationsPanel";
import { EvaluationDetailPanel } from "@/views/TestSuites/components/EvaluationDetailPanel";

// The evaluations API is gated on this permission (the builder itself only needs
// read:llm_analyst), so a user who can edit workflows may still lack eval access.
const EVALUATION_PERMISSION = "test:workflow";

interface WorkflowEvaluationsTabProps {
  /** Active workflow id (agent.workflow_id). Undefined while the agent loads or for an unsaved workflow. */
  workflowId?: string;
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
 * swaps to an in-tab detail view on selection — so the whole evaluations flow
 * stays inside the builder without navigating away.
 */
const WorkflowEvaluationsTab: React.FC<WorkflowEvaluationsTabProps> = ({ workflowId }) => {
  const permissions = usePermissions();
  const canEvaluate =
    permissions.includes("*") || permissions.includes(EVALUATION_PERMISSION);
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null);

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
        {selectedEvaluationId ? (
          <EvaluationDetailPanel
            evaluationId={selectedEvaluationId}
            onBack={() => setSelectedEvaluationId(null)}
            backLabel="Back to evaluations"
          />
        ) : (
          <WorkflowEvaluationsPanel
            workflowId={workflowId}
            allowCreate
            onOpenEvaluation={setSelectedEvaluationId}
          />
        )}
      </div>
    </div>
  );
};

export default WorkflowEvaluationsTab;
