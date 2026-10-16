import React, { useEffect, useState } from "react";
import type { TestCase } from "@/interfaces/testSuite.interface";
import type {
  EvaluationActionNodeInfo,
  EvaluationAgentInfo,
  EvaluationRouterInfo,
  EvaluationStateKeyInfo,
  RuleConversation,
} from "@/interfaces/testEvaluation.interface";
import { getEvaluationToolCatalog } from "@/services/testEvaluations";
import { listTestCases } from "@/services/testSuites";
import { ruleConversations } from "../helpers/datasetConversations";

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

/** The dataset's turns, loaded while enabled; ready once this dataset's turns have arrived. */
export const useDatasetCases = (
  suiteId: string | undefined,
  enabled: boolean,
): { cases: TestCase[]; ready: boolean } => {
  const [state, setState] = useState<{ cases: TestCase[]; loadedFor: string | null }>({
    cases: [],
    loadedFor: null,
  });
  useEffect(() => {
    if (!enabled || !suiteId || suiteId === "none") {
      setState({ cases: [], loadedFor: null });
      return;
    }
    let cancelled = false;
    listTestCases(suiteId)
      .then((loaded) => {
        if (!cancelled) setState({ cases: loaded ?? [], loadedFor: suiteId });
      })
      .catch(() => {
        if (!cancelled) setState({ cases: [], loadedFor: null });
      });
    return () => {
      cancelled = true;
    };
  }, [suiteId, enabled]);
  return { cases: state.cases, ready: enabled && Boolean(suiteId) && state.loadedFor === suiteId };
};

/** Imported conversations for specific-turn targeting, derived from the dataset's turns. */
export const useRuleConversations = (cases: TestCase[]): RuleConversation[] =>
  React.useMemo(() => ruleConversations(cases), [cases]);
