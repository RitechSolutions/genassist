import React from "react";
import { Navigate, useParams } from "react-router-dom";

/** The old link to a workflow's evaluations (`/tests/evaluations/workflows/:workflowId`) opens it on the overview. */
const WorkflowEvaluationsPage: React.FC = () => {
  const { workflowId = "" } = useParams();
  return <Navigate to={`/tests/evaluations?workflow=${encodeURIComponent(workflowId)}`} replace />;
};

export default WorkflowEvaluationsPage;
