import React from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { PageLayout } from "@/components/PageLayout";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { useFeatureFlag } from "@/context/FeatureFlagContext";
import { FeatureFlags } from "@/config/featureFlags";
import { WorkflowEvaluationsPanel } from "../components/WorkflowEvaluationsPanel";

/**
 * Standalone route for a workflow's evaluations (`/tests/evaluations/workflows/:workflowId`).
 * Thin wrapper: the list itself lives in WorkflowEvaluationsPanel, which is shared
 * with the workflow builder's Evaluations tab. Creation stays on the overview here
 * (the tab enables in-context creation via the panel's `allowCreate` prop).
 * With checks on, the overview shows every workflow's evaluations, so the link opens it there.
 */
const WorkflowEvaluationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { workflowId = "" } = useParams();
  const checksEnabled = useFeatureFlagVisible(FeatureFlags.EVALUATIONS.CHECKS);
  const { hydrated } = useFeatureFlag();

  if (!hydrated) return null;
  if (checksEnabled) {
    return <Navigate to={`/tests/evaluations?workflow=${encodeURIComponent(workflowId)}`} replace />;
  }

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
