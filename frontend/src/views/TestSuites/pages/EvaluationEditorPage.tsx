import React from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import { EvaluationEditorView } from "../components/EvaluationEditorView";

/** Makes an evaluation (`/tests/evaluations/new?workflow=`) or edits one (`/:evaluationId/edit`). */
const EvaluationEditorPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { evaluationId } = useParams<{ evaluationId?: string }>();
  const [searchParams] = useSearchParams();

  // Back to where the person came from, or in its place to the evaluation or the list when opened directly.
  const leave = () => {
    if (location.key !== "default") navigate(-1);
    else navigate(evaluationId ? `/tests/evaluations/${evaluationId}` : "/tests/evaluations", { replace: true });
  };

  return (
    <PageLayout>
      <EvaluationEditorView
        evaluationId={evaluationId}
        workflowId={searchParams.get("workflow") ?? undefined}
        onCancel={leave}
        // An edit returns where it began; a new evaluation opens in place of the editor.
        onDone={(id) => (evaluationId ? leave() : navigate(`/tests/evaluations/${id}`, { replace: true }))}
      />
    </PageLayout>
  );
};

export default EvaluationEditorPage;
