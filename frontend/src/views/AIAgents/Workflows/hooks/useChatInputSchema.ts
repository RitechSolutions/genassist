import { useCallback } from "react";
import { useReactFlow } from "reactflow";
import { NodeSchema } from "../types/schemas";

/**
 * Reusable hook to get the input schema from the first connected ChatInputNode in the flow.
 * Optionally accepts a node id for future extensibility.
 */
export function useChatInputSchema(nodeId?: string): NodeSchema | null {
  const { getNodes, getEdges } = useReactFlow();

  const getChatInputSchema = useCallback(() => {
    const nodes = getNodes();
    // Find the first ChatInputNode
    const chatInputNode = nodes.find((node) => node.type === "chatInputNode");
    if (chatInputNode) {
      return chatInputNode.data.inputSchema as NodeSchema;
    }
    return null;
  }, [getNodes, getEdges, nodeId]);

  return getChatInputSchema();
} 