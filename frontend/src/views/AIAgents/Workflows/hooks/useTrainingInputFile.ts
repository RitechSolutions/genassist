import { useReactFlow } from "reactflow";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { extractDynamicVariables, getValueFromPath } from "../utils/helpers";
import { ResolvedInputFile, resolveTrainingInputFile } from "../utils/trainingInputFile";

/**
 * Resolves a training node's File URL (normally "{{source.data_path}}") to the
 * file its Analyze and step previews should read - see resolveTrainingInputFile.
 */
export const useTrainingInputFile = (nodeId: string | undefined) => {
  // Read the graph when resolving, not on every render, so an open dialog
  // doesn't re-render while nodes are dragged.
  const { getNodes, getEdges } = useReactFlow();
  const { getAvailableDataForNode, getLatestNodeOutput } = useWorkflowExecution();

  const fillVariables = (url: string): string => {
    const variables = extractDynamicVariables(url);
    if (variables.size === 0 || !nodeId) return url;
    const availableData = getAvailableDataForNode(nodeId);
    if (!availableData) return url;
    let filled = url;
    variables.forEach((variable) => {
      const value = getValueFromPath(availableData, variable);
      if (value === undefined) return;
      const stringValue =
        typeof value === "string"
          ? value
          : typeof value === "object"
          ? JSON.stringify(value)
          : String(value);
      filled = filled.split(`{{${variable}}}`).join(stringValue);
    });
    return filled;
  };

  return (fileUrl: string): ResolvedInputFile =>
    resolveTrainingInputFile({
      fileUrl,
      nodeId,
      nodes: getNodes(),
      edges: getEdges(),
      getLatestOutput: getLatestNodeOutput,
      fillVariables,
    });
};
