import { useCallback, useEffect, useRef, useState } from "react";
import { ChatService, type ChatMessage } from "genassist-chat-react";
import { Node, Edge } from "reactflow";
import { v4 as uuidv4 } from "uuid";
import {
  serializeCanvasContext,
  parseAgentActions,
  createNodeFromAction,
  type AssistantMessage,
  type ParsedAction,
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
  const chatRef = useRef<ChatService | null>(null);
  const isMountedRef = useRef(true);
  const isStartingRef = useRef(false);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const executedActionsRef = useRef<Set<string>>(new Set());

  // Keep refs in sync so callbacks always see current canvas state
  nodesRef.current = nodes;
  edgesRef.current = edges;

  const baseUrl = (import.meta.env.VITE_ONBOARDING_API_URL as string) || "";
  const apiKey = (import.meta.env.VITE_ONBOARDING_CHAT_APIKEY as string) || "";
  const tenant =
    (localStorage.getItem("tenant_id") as string | null) || undefined;

  const hasConfig = Boolean(baseUrl && apiKey);

  // Restore node functions after adding to canvas
  const restoreNode = useCallback(
    (node: Node): Node => ({
      ...node,
      data: { ...node.data, updateNodeData },
    }),
    [updateNodeData],
  );

  // Execute parsed actions on the canvas
  const executeActions = useCallback(
    (actions: ParsedAction[]) => {
      for (const action of actions) {
        const actionKey = `${action.nodeType}-${action.label}-${action.connectTo}`;
        if (executedActionsRef.current.has(actionKey)) continue;
        executedActionsRef.current.add(actionKey);

        const { node, edge } = createNodeFromAction(
          action,
          nodesRef.current,
        );
        if (node) {
          const restored = restoreNode(node);
          setNodes((nds) => {
            const updated = [...nds, restored];
            nodesRef.current = updated;
            return updated;
          });
        }
        if (edge) {
          setEdges((eds) => {
            const updated = [...eds, edge];
            edgesRef.current = updated;
            return updated;
          });
        }
      }
    },
    [restoreNode, setNodes, setEdges],
  );

  // Initialize ChatService
  useEffect(() => {
    if (!hasConfig) return;

    const chat = new ChatService(baseUrl, apiKey, undefined, tenant);
    chatRef.current = chat;

    chat.setMessageHandler((message: ChatMessage) => {
      if (!isMountedRef.current) return;
      if (message.speaker === "agent") {
        setIsThinking(false);
        const { cleanText, actions } = parseAgentActions(message.text);

        // Update or add the latest agent message
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.speaker === "agent") {
            // Replace streaming message
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
      }
    });

    return () => {
      chat.disconnect();
      chatRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, apiKey, tenant, hasConfig]);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Reset conversation when the workflow scope changes (e.g. switching agents/workflows)
  const prevScopeRef = useRef(workflowScopeId);
  useEffect(() => {
    if (prevScopeRef.current !== undefined && workflowScopeId !== prevScopeRef.current) {
      setMessages([]);
      executedActionsRef.current.clear();
      const chat = chatRef.current;
      if (chat) {
        chat.resetChatConversation();
      }
    }
    prevScopeRef.current = workflowScopeId;
  }, [workflowScopeId]);

  const startConversationIfNeeded = useCallback(async () => {
    const chat = chatRef.current;
    if (!chat || isStartingRef.current) return;

    const existing = chat.getConversationId?.();
    if (existing) return;

    isStartingRef.current = true;
    try {
      await chat.startConversation(undefined);
    } finally {
      isStartingRef.current = false;
    }
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !chatRef.current) return;

      // Add user message to chat
      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), speaker: "customer", text: trimmed },
      ]);
      setIsThinking(true);
      // Reset executed actions for this new exchange
      executedActionsRef.current.clear();

      // Build context prefix
      const context = serializeCanvasContext(
        nodesRef.current,
        edgesRef.current,
      );
      const fullMessage = `${context}\n\n${trimmed}`;

      try {
        await startConversationIfNeeded();
        await chatRef.current.sendMessage(fullMessage);
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
    [startConversationIfNeeded],
  );

  const clearHistory = useCallback(() => {
    setMessages([]);
    const chat = chatRef.current;
    if (chat) {
      chat.resetChatConversation();
    }
  }, []);

  return {
    messages,
    isThinking,
    sendMessage,
    clearHistory,
    hasConfig,
  };
}
