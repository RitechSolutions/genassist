import React, { useCallback, useMemo, useRef } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { PageLayout } from "@/components/PageLayout";
import { EvaluationDetailPanel } from "../components/EvaluationDetailPanel";
import {
  locationFromParams,
  paramsFromLocation,
  type ResultsLocation,
  type ResultsMove,
} from "../helpers/resultsLocation";

const UNASSIGNED = "unassigned";

/**
 * Standalone route for a single evaluation (`/tests/evaluations/:evaluationId`).
 * Thin wrapper: the detail view lives in EvaluationDetailPanel, which is shared
 * with the workflow builder's Evaluations tab. Back returns to the evaluation's
 * workflow (resolved once the panel loads it). The run, conversation or
 * comparison open in it lives in the URL, so it can be linked and the browser's
 * back button steps out of it.
 */
const EvaluationDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { evaluationId } = useParams<{ evaluationId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  // The panel reports the evaluation's workflow id once loaded; back uses it.
  const workflowIdRef = useRef<string | null>(null);

  const handleWorkflowResolved = useCallback((workflowId: string | null) => {
    workflowIdRef.current = workflowId;
  }, []);

  // Every workflow's evaluations are on the overview, opened at this one.
  const handleBack = useCallback(() => {
    const workflow = workflowIdRef.current ?? UNASSIGNED;
    navigate(`/tests/evaluations?workflow=${encodeURIComponent(workflow)}`);
  }, [navigate]);

  const search = searchParams.toString();
  const resultsView = useMemo(() => locationFromParams(new URLSearchParams(search)), [search]);

  // Each view remembers the one it was opened from, so Back to it steps back in history.
  const parent = (location.state as { resultsParent?: string } | null)?.resultsParent;

  // Moving within a view (the next conversation, another run to compare with) replaces the
  // history entry, so the browser's back button leaves the view instead of retracing it.
  const handleResultsViewChange = useCallback(
    (view: ResultsLocation | null, move?: ResultsMove) => {
      const target = paramsFromLocation(view);
      if (move?.back && parent === target.toString()) {
        navigate(-1);
        return;
      }
      if (move?.back || move?.replace) {
        setSearchParams(target, { replace: true, state: move.replace ? location.state : null });
        return;
      }
      setSearchParams(target, { state: { resultsParent: search } });
    },
    [navigate, parent, search, setSearchParams, location.state],
  );

  return (
    <PageLayout>
      <EvaluationDetailPanel
        evaluationId={evaluationId ?? ""}
        onBack={handleBack}
        onWorkflowResolved={handleWorkflowResolved}
        resultsView={resultsView}
        onResultsViewChange={handleResultsViewChange}
      />
    </PageLayout>
  );
};

export default EvaluationDetailPage;
