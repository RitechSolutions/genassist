import React, { useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { PageLayout } from "@/components/PageLayout";
import { EvaluationDetailPanel } from "../components/EvaluationDetailPanel";

const UNASSIGNED = "unassigned";

/**
 * Standalone route for a single evaluation (`/tests/evaluations/:evaluationId`).
 * Thin wrapper: the detail view lives in EvaluationDetailPanel, which is shared
 * with the workflow builder's Evaluations tab. Back navigates to the evaluation's
 * workflow page (resolved once the panel loads it).
 */
const EvaluationDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { evaluationId } = useParams<{ evaluationId: string }>();
  // The panel reports the evaluation's workflow id once loaded; back uses it.
  const workflowIdRef = useRef<string | null>(null);

  const handleWorkflowResolved = useCallback((workflowId: string | null) => {
    workflowIdRef.current = workflowId;
  }, []);

  const handleBack = useCallback(() => {
    navigate(`/tests/evaluations/workflows/${workflowIdRef.current ?? UNASSIGNED}`);
  }, [navigate]);

  return (
    <PageLayout>
      <EvaluationDetailPanel
        evaluationId={evaluationId ?? ""}
        onBack={handleBack}
        onWorkflowResolved={handleWorkflowResolved}
      />
    </PageLayout>
  );
};

export default EvaluationDetailPage;
