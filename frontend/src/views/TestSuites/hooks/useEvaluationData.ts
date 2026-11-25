import { useCallback, useEffect, useState } from "react";
import type { TestCase } from "@/interfaces/testSuite.interface";
import type {
  EvaluationActionNodeInfo,
  EvaluationAgentInfo,
  EvaluationRouterInfo,
  EvaluationStateKeyInfo,
} from "@/interfaces/testEvaluation.interface";
import { getEvaluationToolCatalog } from "@/services/testEvaluations";
import { listTestCases } from "@/services/testSuites";

/** The evaluations page's per-workflow summaries; refreshed when a workflow's evaluations change. */
export const WORKFLOW_SUMMARIES_QUERY_KEY = ["workflow-evaluation-summaries"];

export interface EvaluationCatalog {
  agents: EvaluationAgentInfo[];
  routers: EvaluationRouterInfo[];
  actionNodes: EvaluationActionNodeInfo[];
  stateKeys: EvaluationStateKeyInfo[];
  loading: boolean;
  error: string | null;
  /** True once this workflow's catalog has loaded, so an empty one really is empty. */
  ready: boolean;
}

type CatalogState = Omit<EvaluationCatalog, "ready"> & { loadedFor: string | null };

const EMPTY_CATALOG: CatalogState = {
  agents: [],
  routers: [],
  actionNodes: [],
  stateKeys: [],
  loading: false,
  error: null,
  loadedFor: null,
};

/** The workflow's agents, routers, steps and remembered values, loaded while enabled. */
export const useEvaluationCatalog = (workflowId: string | undefined, enabled: boolean): EvaluationCatalog => {
  const [catalog, setCatalog] = useState<CatalogState>(EMPTY_CATALOG);
  useEffect(() => {
    if (!enabled || !workflowId) {
      setCatalog(EMPTY_CATALOG);
      return;
    }
    let cancelled = false;
    setCatalog((previous) => ({ ...previous, loading: true, error: null }));
    getEvaluationToolCatalog(workflowId)
      .then((loaded) => {
        if (cancelled) return;
        setCatalog({
          agents: loaded.agents ?? [],
          routers: loaded.routers ?? [],
          actionNodes: loaded.action_nodes ?? [],
          stateKeys: loaded.state_keys ?? [],
          loading: false,
          error: null,
          loadedFor: workflowId,
        });
      })
      .catch(() => {
        if (!cancelled) setCatalog({ ...EMPTY_CATALOG, error: "Failed to load workflow nodes" });
      });
    return () => {
      cancelled = true;
    };
  }, [workflowId, enabled]);
  const { loadedFor, ...rest } = catalog;
  return { ...rest, ready: enabled && Boolean(workflowId) && loadedFor === workflowId };
};

const NO_CASES: TestCase[] = [];

/** The dataset's turns, loaded while enabled; ready once this dataset's turns have arrived. */
export const useDatasetCases = (
  suiteId: string | undefined,
  enabled: boolean,
): { cases: TestCase[]; ready: boolean; failed: boolean; retry: () => void } => {
  const [state, setState] = useState<{ cases: TestCase[]; loadedFor: string | null; failedFor: string | null }>({
    cases: [],
    loadedFor: null,
    failedFor: null,
  });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled || !suiteId || suiteId === "none") {
      setState({ cases: [], loadedFor: null, failedFor: null });
      return;
    }
    let cancelled = false;
    setState((previous) => ({ ...previous, failedFor: null }));
    listTestCases(suiteId)
      .then((loaded) => {
        if (!cancelled) setState({ cases: loaded ?? [], loadedFor: suiteId, failedFor: null });
      })
      .catch(() => {
        if (!cancelled) setState({ cases: [], loadedFor: null, failedFor: suiteId });
      });
    return () => {
      cancelled = true;
    };
  }, [suiteId, enabled, attempt]);
  // Another dataset's turns are never handed out while this one loads.
  const ready = enabled && Boolean(suiteId) && state.loadedFor === suiteId;
  const failed = enabled && Boolean(suiteId) && state.failedFor === suiteId;
  const retry = useCallback(() => setAttempt((count) => count + 1), []);
  return { cases: ready ? state.cases : NO_CASES, ready, failed, retry };
};
