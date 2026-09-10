import { useQuery } from "@tanstack/react-query";
import { getPromptHistory } from "@/services/promptEditor";

/** Cache prefix; invalidates all nodes since legacy rows are shared */
export const promptHistoryWorkflowKey = (workflowId: string) =>
  ["promptHistory", workflowId] as const;

export const promptHistoryKey = (
  workflowId: string,
  nodeId: string,
  promptField: string,
) => [...promptHistoryWorkflowKey(workflowId), nodeId, promptField] as const;

export const usePromptHistory = (
  workflowId: string,
  nodeId: string,
  promptField: string,
) => {
  const query = useQuery({
    queryKey: promptHistoryKey(workflowId, nodeId, promptField),
    queryFn: () => getPromptHistory(workflowId, nodeId, promptField),
    // node_missing and dataset links change between opens (workflow saves, relinks).
    // Cached data is first-paint only.
    staleTime: 0,
  });

  return {
    ...query,
    history: query.data ?? null,
    isForbidden: query.data === null,
  };
};
