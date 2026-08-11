import React from "react";
import { useNavigate, useParams } from "react-router-dom";

import { PageLayout } from "@/components/PageLayout";
import { WorkflowEvaluationsPanel } from "../components/WorkflowEvaluationsPanel";

/**
 * Standalone route for a workflow's evaluations (`/tests/evaluations/workflows/:workflowId`).
 * Thin wrapper: the list itself lives in WorkflowEvaluationsPanel, which is shared
 * with the workflow builder's Evaluations tab. Creation stays on the overview here
 * (the tab enables in-context creation via the panel's `allowCreate` prop).
 */
const WorkflowEvaluationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { workflowId = "" } = useParams();

  return (
    <PageLayout>
      <WorkflowEvaluationsPanel
        workflowId={workflowId}
        onBack={() => navigate("/tests/evaluations")}
        onOpenEvaluation={(evaluationId) =>
          navigate(`/tests/evaluations/${evaluationId}`)
        }
      />
    </PageLayout>
  );
};

export default WorkflowEvaluationsPage;
