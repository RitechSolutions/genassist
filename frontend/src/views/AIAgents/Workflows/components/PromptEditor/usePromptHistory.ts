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
  nodeType?: string,
) => {
  const query = useQuery({
    // nodeType last so promptHistoryKey stays a usable prefix
    queryKey: [...promptHistoryKey(workflowId, nodeId, promptField), nodeType ?? null],
    queryFn: () => getPromptHistory(workflowId, nodeId, promptField, nodeType),
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
