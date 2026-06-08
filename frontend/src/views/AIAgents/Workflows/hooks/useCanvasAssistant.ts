import { useCallback, useEffect, useRef, useState } from "react";
import { type ChatMessage } from "genassist-chat-react";
import { Node, Edge } from "reactflow";
import { v4 as uuidv4 } from "uuid";
import { useChatService } from "@/hooks/useChatService";
import {
  serializeCanvasContext,
  parseAgentActions,
  createNodeFromAction,
  type AssistantMessage,
  type ParsedAction,
  type AddNodeAction,
  type UpdateNodeAction,
  type RemoveNodeAction,
  type RemoveEdgeAction,
} from "../utils/assistantActionParser";

interface UseCanvasAssistantArgs {
  nodes: Node[];
  edges: Edge[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  updateNodeData: (nodeId: string, data: Record<string, unknown>) => void;
  /** When this changes the conversation resets so context from a previous workflow doesn't leak. */
  workflowScopeId?: string;
}

export function useCanvasAssistant({
  nodes,
  edges,
  setNodes,
  setEdges,
  updateNodeData,
  workflowScopeId,
}: UseCanvasAssistantArgs) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const suppressWelcomeRef = useRef(false);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const executedActionsRef = useRef<Set<string>>(new Set());

  // Keep refs in sync so callbacks always see current canvas state
  nodesRef.current = nodes;
  edgesRef.current = edges;

  // Restore node functions after adding to canvas
  const restoreNode = useCallback(
    (node: Node): Node => ({
      ...node,
      data: { ...node.data, updateNodeData },
    }),
    [updateNodeData],
  );

  // Build a dedup key for any action
  const actionKey = (action: ParsedAction): string => {
    switch (action.type) {
      case "add_node":
        return `add-${action.nodeType}-${action.label}-${action.connectTo}-${action.thenConnectTo}-${action.asToolFor}`;
      case "update_node":
        return `update-${action.nodeId}-${JSON.stringify(action.updates)}`;
      case "remove_node":
        return `remove-${action.nodeId}`;
      case "remove_edge":
        return `remove-edge-${action.fromNodeId}-${action.toNodeId}`;
    }
  };

  // Execute parsed actions on the canvas
  const executeActions = useCallback(
    (actions: ParsedAction[]) => {
      // Track nodes added in this batch so label resolution works across sequential ADD_NODEs
      let batchNodes: Node[] = [...nodesRef.current];

      for (const action of actions) {
        const key = actionKey(action);
        if (executedActionsRef.current.has(key)) continue;
        executedActionsRef.current.add(key);

        if (action.type === "add_node") {
          const { nodes: newNodes, edges: newEdges } = createNodeFromAction(
            action as AddNodeAction,
            batchNodes,
          );
          if (newNodes.length > 0) {
            const restored = newNodes.map(restoreNode);
            batchNodes = [...batchNodes, ...restored];
            setNodes((nds) => {
              const updated = [...nds, ...restored];
              nodesRef.current = updated;
              return updated;
            });
          }
          if (newEdges.length > 0) {
            setEdges((eds) => {
              const updated = [...eds, ...newEdges];
              edgesRef.current = updated;
              return updated;
            });
          }
        } else if (action.type === "update_node") {
          const { nodeId, updates } = action as UpdateNodeAction;
          setNodes((nds) => {
            const updated = nds.map((n) =>
              n.id === nodeId ? { ...n, data: { ...n.data, ...updates } } : n,
            );
            nodesRef.current = updated;
            return updated;
          });
        } else if (action.type === "remove_node") {
          const { nodeId } = action as RemoveNodeAction;
          setNodes((nds) => {
            const updated = nds.filter((n) => n.id !== nodeId);
            nodesRef.current = updated;
            return updated;
          });
          // Also remove edges connected to the removed node
          setEdges((eds) => {
            const updated = eds.filter(
              (e) => e.source !== nodeId && e.target !== nodeId,
            );
            edgesRef.current = updated;
            return updated;
          });
        } else if (action.type === "remove_edge") {
          const { fromNodeId, toNodeId } = action as RemoveEdgeAction;
          setEdges((eds) => {
            const updated = eds.filter(
              (e) => !(e.source === fromNodeId && e.target === toNodeId),
            );
            edgesRef.current = updated;
            return updated;
          });
        }
      }
    },
    [restoreNode, setNodes, setEdges],
  );

  // ── Message handler ──
  const handleMessage = useCallback(
    (message: ChatMessage) => {
      if (message.speaker === "agent") {
        if (suppressWelcomeRef.current) {
          suppressWelcomeRef.current = false;
          return;
        }

        setIsThinking(false);
        const { cleanText, actions } = parseAgentActions(message.text);

        // Update or add the latest agent message
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.speaker === "agent") {
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, text: cleanText, actions },
            ];
          }
          return [
            ...prev,
            { id: uuidv4(), speaker: "agent", text: cleanText, actions },
          ];
        });

        if (actions.length > 0) {
          executeActions(actions);
        }
      } else if (message.speaker === "special") {
        setIsThinking(false);
        setMessages((prev) => [
          ...prev,
          { id: uuidv4(), speaker: "agent", text: message.text },
        ]);
      }
    },
    [executeActions],
  );

  const { sendMessage: chatSend, resetConversation, hasConfig, chatRef } = useChatService({
    onMessage: handleMessage,
    scopeId: workflowScopeId,
  });

  // Reset local state when scope changes
  const prevScopeRef = useRef(workflowScopeId);
  useEffect(() => {
    if (prevScopeRef.current !== undefined && workflowScopeId !== prevScopeRef.current) {
      setMessages([]);
      executedActionsRef.current.clear();
    }
    prevScopeRef.current = workflowScopeId;
  }, [workflowScopeId]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), speaker: "customer", text: trimmed },
      ]);
      setIsThinking(true);
      executedActionsRef.current.clear();

      // Build context prefix
      const context = serializeCanvasContext(
        nodesRef.current,
        edgesRef.current,
      );
      const fullMessage = `${context}\n\n${trimmed}`;

      try {
        // Only suppress the welcome message when we're actually starting a new conversation;
        // otherwise the first real agent response would be swallowed.
        if (!chatRef.current?.getConversationId?.()) {
          suppressWelcomeRef.current = true;
        }
        await chatSend(fullMessage);
      } catch (err) {
        setIsThinking(false);
        const errMsg =
          err instanceof Error ? err.message : "Failed to send message.";
        setMessages((prev) => [
          ...prev,
          { id: uuidv4(), speaker: "agent", text: errMsg },
        ]);
      }
    },
    [chatSend],
  );

  const clearHistory = useCallback(() => {
    setMessages([]);
    resetConversation();
  }, [resetConversation]);

  return {
    messages,
    isThinking,
    sendMessage,
    clearHistory,
    hasConfig,
  };
}
