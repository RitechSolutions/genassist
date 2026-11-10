import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type ChatMessage, type StreamEvent } from "genassist-chat-react";
import { Node, Edge } from "reactflow";
import { v4 as uuidv4 } from "uuid";
import { useChatService, type SavedConversation } from "@/hooks/useChatService";
import {
  applyBuilderOperations,
  getBuilderDraft,
  putBuilderDraft,
  runAssistAction,
  type AssistAction,
  type AssistProposal,
  type BuilderCanvasSnapshot,
  type BuilderDraft,
} from "@/services/workflowBuilder";
import {
  applyLiveStreamEvent,
  changesAffectLayout,
  clearAiChanges,
  markAiChanges,
  mergeDraftNodes,
  newLiveTurn,
  reportableIssues,
  serializeCanvasForDraft,
  settleLiveTurn,
  type AssistantMessage,
  type LiveTurn,
} from "../utils/assistantDraft";

interface UseCanvasAssistantArgs {
  nodes: Node[];
  edges: Edge[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  /** Rebuilds what plain JSON nodes lack (registry handles, data callbacks). */
  hydrateNodes: (nodes: Node[]) => Node[];
  /**
   * Called after a turn in which the assistant added or removed nodes or
   * connections, so the canvas can auto-arrange once the new nodes are rendered.
   */
  onStructureChanged?: () => void;
  /** The person's latest (or pinned) test run on the canvas, shared with the assistant on each message. */
  getLastTestRun?: () => BuilderCanvasSnapshot["last_test_run"];
  /** The node the user has selected, so "this node" means something to the assistant. */
  selectedNodeId?: string | null;
  /** When this changes the conversation resets so context from a previous workflow doesn't leak. */
  workflowScopeId?: string;
}

/** The assistant's last change to the canvas, shown highlighted until kept or undone. */
export interface PendingChange {
  count: number;
  summary: string;
}

// ── Per-agent persistence (browser storage, no database) ──
// The conversation id is what keeps the builder's memory and draft on the
// server; the messages are kept so the chat looks the same when you come back.

interface SavedChat {
  conversation: SavedConversation | null;
  messages: AssistantMessage[];
  savedAt: number;
}

const SAVED_MESSAGE_LIMIT = 80;

const chatStorageKey = (scopeId: string) => {
  let tenant = "";
  try {
    tenant = localStorage.getItem("tenant_id") ?? "";
  } catch {
    // ignore
  }
  return `genassist:workflow-builder-chat:${tenant}:${scopeId}`;
};

function loadSavedChat(scopeId?: string): SavedChat | null {
  if (!scopeId) return null;
  try {
    const raw = localStorage.getItem(chatStorageKey(scopeId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SavedChat;
    if (!Array.isArray(parsed.messages)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveChat(scopeId: string | undefined, chat: SavedChat): void {
  if (!scopeId) return;
  try {
    const messages = chat.messages.slice(-SAVED_MESSAGE_LIMIT).map((msg) => {
      // Undo needs the canvas snapshot, which is not kept across visits.
      const { undoable: _u, arrivedAt: _a, ...rest } = msg;
      return rest;
    });
    localStorage.setItem(chatStorageKey(scopeId), JSON.stringify({ ...chat, messages }));
  } catch {
    // Storage full or unavailable: the chat simply will not be restored.
  }
}

function forgetChat(scopeId?: string): void {
  if (!scopeId) return;
  try {
    localStorage.removeItem(chatStorageKey(scopeId));
  } catch {
    // ignore
  }
}

/**
 * Chat with the Workflow Builder agent about the workflow on the canvas.
 *
 * Each message is a round trip through a server-side draft: the canvas is
 * uploaded as the draft, the agent edits it with its tools (every edit is
 * validated on the server), and the result is read back and applied here.
 * Nothing is parsed out of the agent's reply text.
 *
 * Focused actions (explain, improve a prompt, optimize, review...) take one
 * model call on the server without a builder turn; their proposals are applied
 * only when the person approves them.
 */
export function useCanvasAssistant({
  nodes,
  edges,
  setNodes,
  setEdges,
  hydrateNodes,
  onStructureChanged,
  getLastTestRun,
  selectedNodeId,
  workflowScopeId,
}: UseCanvasAssistantArgs) {
  // What this agent's chat looked like last time; read once per scope.
  const savedChat = useMemo(() => loadSavedChat(workflowScopeId), [workflowScopeId]);
  const [messages, setMessages] = useState<AssistantMessage[]>(() => savedChat?.messages ?? []);
  const [isThinking, setIsThinking] = useState(false);
  // The turn in progress: narrated steps, thoughts and the reply as it streams in.
  const [liveTurn, setLiveTurn] = useState<LiveTurn | null>(null);
  const liveTurnRef = useRef<LiveTurn | null>(null);
  const updateLiveTurn = useCallback((turn: LiveTurn | null) => {
    liveTurnRef.current = turn;
    setLiveTurn(turn);
  }, []);
  const [simulateActions, setSimulateActions] = useState(true);
  const [pendingChange, setPendingChange] = useState<PendingChange | null>(null);
  const suppressWelcomeRef = useRef(false);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const selectedNodeIdRef = useRef(selectedNodeId);
  const simulateRef = useRef(simulateActions);
  // Draft revision already reflected on the canvas; a higher one means the agent changed something.
  const appliedRevisionRef = useRef(0);
  // The canvas as it was before the assistant's last change, for Undo.
  const beforeChangeRef = useRef<{ nodes: Node[]; edges: Edge[] } | null>(null);
  // The canvas as it was when each of the person's messages was sent, keyed by
  // that message's id, so any turn's changes can be undone from the message itself.
  const turnSnapshotsRef = useRef<Map<string, { nodes: Node[]; edges: Edge[] }>>(new Map());
  const currentTurnIdRef = useRef<string | null>(null);

  const beginTurn = useCallback((messageId: string) => {
    turnSnapshotsRef.current.set(messageId, {
      nodes: clearAiChanges(nodesRef.current),
      edges: edgesRef.current,
    });
    currentTurnIdRef.current = messageId;
  }, []);

  // Keep refs in sync so callbacks always see current canvas state
  nodesRef.current = nodes;
  edgesRef.current = edges;
  selectedNodeIdRef.current = selectedNodeId;
  simulateRef.current = simulateActions;
  const getLastTestRunRef = useRef(getLastTestRun);
  getLastTestRunRef.current = getLastTestRun;

  // Mirror of `messages` that is current the moment it is written, so a reply
  // can be tied to its message id without waiting for a render.
  const messagesRef = useRef<AssistantMessage[]>(savedChat?.messages ?? []);
  const updateMessages = useCallback(
    (update: (prev: AssistantMessage[]) => AssistantMessage[]) => {
      messagesRef.current = update(messagesRef.current);
      setMessages(messagesRef.current);
    },
    []
  );

  const addAgentMessage = useCallback(
    (message: Omit<AssistantMessage, "id" | "speaker">) =>
      updateMessages((prev) => [
        ...prev,
        { id: uuidv4(), speaker: "agent", arrivedAt: Date.now(), ...message },
      ]),
    [updateMessages]
  );

  const snapshot = useCallback(
    () =>
      serializeCanvasForDraft(
        nodesRef.current,
        edgesRef.current,
        selectedNodeIdRef.current,
        getLastTestRunRef.current?.(),
        simulateRef.current
      ),
    []
  );

  const setCanvas = useCallback(
    (nextNodes: Node[], nextEdges: Edge[]) => {
      nodesRef.current = nextNodes;
      edgesRef.current = nextEdges;
      setNodes(nextNodes);
      setEdges(nextEdges);
    },
    [setNodes, setEdges]
  );

  // Put a draft on the canvas, highlighting what changed and remembering the
  // state before it so the person can undo the whole change in one click.
  const applyDraftToCanvas = useCallback(
    (draft: BuilderDraft) => {
      const ids = new Set((draft.nodes as unknown as Node[]).map((n) => n.id));
      const draftEdges = (draft.edges as unknown as Edge[]).filter((e) => ids.has(e.source) && ids.has(e.target));
      const before = {
        nodes: clearAiChanges(nodesRef.current),
        edges: edgesRef.current,
      };
      const merged = hydrateNodes(
        markAiChanges(
          mergeDraftNodes(clearAiChanges(nodesRef.current), draft.nodes as unknown as Node[]),
          draft.changes
        )
      );
      setCanvas(merged, draftEdges);
      if (draft.changes.length > 0) {
        beforeChangeRef.current = before;
        setPendingChange({
          count: draft.changes.length,
          summary: draft.changes.map((c) => c.summary).join("; "),
        });
        const turnId = currentTurnIdRef.current;
        if (turnId) {
          updateMessages((prev) =>
            prev.map((msg) => (msg.id === turnId ? { ...msg, undoable: true, undone: false } : msg))
          );
        }
      }
      if (changesAffectLayout(draft.changes)) onStructureChanged?.();
    },
    [hydrateNodes, onStructureChanged, setCanvas, updateMessages]
  );

  /**
   * Put the canvas back to how it was before the person's message `messageId`
   * was sent, undoing that turn and every turn after it.
   */
  const undoTurn = useCallback(
    (messageId: string) => {
      const snapshot = turnSnapshotsRef.current.get(messageId);
      if (!snapshot) return false;
      beforeChangeRef.current = null;
      setPendingChange(null);
      setCanvas(hydrateNodes(snapshot.nodes), snapshot.edges);
      const index = messagesRef.current.findIndex((msg) => msg.id === messageId);
      updateMessages((prev) =>
        prev.map((msg, i) =>
          i >= index && msg.speaker === "customer" && msg.undoable ? { ...msg, undone: true } : msg
        )
      );
      for (const [id] of turnSnapshotsRef.current) {
        const position = messagesRef.current.findIndex((msg) => msg.id === id);
        if (position > index) turnSnapshotsRef.current.delete(id);
      }
      const prompt = messagesRef.current[index]?.text ?? "";
      addAgentMessage({
        text: `Undone. The canvas is back to how it was before "${prompt.length > 60 ? `${prompt.slice(0, 60)}…` : prompt}".`,
      });
      return true;
    },
    [addAgentMessage, hydrateNodes, setCanvas, updateMessages]
  );

  const keepChanges = useCallback(() => {
    beforeChangeRef.current = null;
    setPendingChange(null);
    setCanvas(clearAiChanges(nodesRef.current), edgesRef.current);
  }, [setCanvas]);

  const undoChanges = useCallback(() => {
    const before = beforeChangeRef.current;
    beforeChangeRef.current = null;
    setPendingChange(null);
    if (!before) return false;
    setCanvas(hydrateNodes(before.nodes), before.edges);
    addAgentMessage({ text: "Undone. The canvas is back to how it was before my last change." });
    return true;
  }, [addAgentMessage, hydrateNodes, setCanvas]);

  // Read the draft after the agent's turn and bring the canvas in line with it.
  // A question the agent asked rides on the draft too, without a revision change.
  const applyDraft = useCallback(
    async (conversationId: string, messageId: string) => {
      const draft = await getBuilderDraft(conversationId);
      if (!draft) return;
      const changed = draft.revision > appliedRevisionRef.current;
      if (changed) {
        appliedRevisionRef.current = draft.revision;
        applyDraftToCanvas(draft);
      }
      const question = draft.question ?? undefined;
      if (!changed && !question) return;
      updateMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                ...(changed ? { changes: draft.changes, issues: reportableIssues(draft) } : {}),
                ...(question ? { question } : {}),
              }
            : msg
        )
      );
    },
    [applyDraftToCanvas, updateMessages]
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
        // What the assistant did on the way to this reply stays with it.
        const turn = liveTurnRef.current;
        const work = turn ? settleLiveTurn(turn) : {};
        const streamed = Boolean(turn && turn.text.trim());
        updateLiveTurn(null);

        // Update or add the latest agent message
        const last = messagesRef.current[messagesRef.current.length - 1];
        const messageId = last?.speaker === "agent" && !last.proposals && !last.findings ? last.id : uuidv4();
        updateMessages((prev) =>
          last?.id === messageId
            ? [...prev.slice(0, -1), { ...last, text: message.text, ...work, streamed }]
            : [...prev, { id: messageId, speaker: "agent", text: message.text, arrivedAt: Date.now(), ...work, streamed }]
        );

        const conversationId = chatRef.current?.getConversationId?.();
        if (conversationId) {
          applyDraft(conversationId, messageId).catch(() => {
            addAgentMessage({
              text: "I couldn't load the updated workflow, so the canvas was not changed.",
            });
          });
        }
      } else if (message.speaker === "special") {
        setIsThinking(false);
        updateLiveTurn(null);
        addAgentMessage({ text: message.text });
      }
    },
    // chatRef is a stable ref from useChatService
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [applyDraft, addAgentMessage, updateMessages, updateLiveTurn]
  );

  // Progress frames of the streamed turn: narrated steps, thoughts, reply text.
  const handleStream = useCallback(
    (event: StreamEvent) => {
      const current = liveTurnRef.current ?? newLiveTurn();
      updateLiveTurn(applyLiveStreamEvent(current, event));
    },
    [updateLiveTurn]
  );

  const {
    sendMessage: chatSend,
    resetConversation,
    hasConfig,
    chatRef,
    startConversationIfNeeded,
    getConversationState,
  } = useChatService({
    onMessage: handleMessage,
    onStream: handleStream,
    scopeId: workflowScopeId,
    resume: savedChat?.conversation ?? null,
  });

  // A new scope (another agent) shows that agent's own saved chat, if any.
  const prevScopeRef = useRef(workflowScopeId);
  useEffect(() => {
    if (prevScopeRef.current !== undefined && workflowScopeId !== prevScopeRef.current) {
      updateMessages(() => loadSavedChat(workflowScopeId)?.messages ?? []);
      appliedRevisionRef.current = 0;
      beforeChangeRef.current = null;
      turnSnapshotsRef.current.clear();
      setPendingChange(null);
    }
    prevScopeRef.current = workflowScopeId;
  }, [workflowScopeId, updateMessages]);

  // Keep the saved copy current: every change to the messages, plus the
  // conversation id once one exists.
  useEffect(() => {
    if (!workflowScopeId) return;
    if (messages.length === 0) {
      forgetChat(workflowScopeId);
      return;
    }
    saveChat(workflowScopeId, {
      conversation: getConversationState() ?? savedChat?.conversation ?? null,
      messages,
      savedAt: Date.now(),
    });
  }, [messages, workflowScopeId, getConversationState, savedChat]);

  /**
   * Send a message to the builder. `focusNodeIds` (from @-mentions, a node's
   * menu or a selection) are named in the message so "this step" is unambiguous.
   */
  const sendMessage = useCallback(
    async (text: string, focusNodeIds: string[] = []) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      // A new turn settles the previous change: the canvas as it is now is what the agent edits.
      beforeChangeRef.current = null;
      setPendingChange(null);

      const focusNames = focusNodeIds
        .map((id) => nodesRef.current.find((n) => n.id === id)?.data?.name)
        .filter((name): name is string => typeof name === "string" && name.length > 0);
      const outgoing =
        focusNames.length > 0
          ? `(About the step${focusNames.length > 1 ? "s" : ""} ${focusNames.map((n) => `"${n}"`).join(", ")}) ${trimmed}`
          : trimmed;

      const messageId = uuidv4();
      updateMessages((prev) => [...prev, { id: messageId, speaker: "customer", text: trimmed, nodeIds: focusNodeIds }]);
      beginTurn(messageId);
      setIsThinking(true);
      updateLiveTurn(newLiveTurn());

      try {
        // Only suppress the welcome message when we're actually starting a new conversation;
        // otherwise the first real agent response would be swallowed.
        if (!chatRef.current?.getConversationId?.()) {
          suppressWelcomeRef.current = true;
        }
        await startConversationIfNeeded();
        const conversationId = chatRef.current?.getConversationId?.();
        if (!conversationId) {
          throw new Error("Could not start a conversation with the assistant.");
        }

        // The agent edits a draft of the canvas exactly as it is now, unsaved changes included.
        const uploaded = await putBuilderDraft(conversationId, {
          ...snapshot(),
          selected_node_id: focusNodeIds[0] ?? selectedNodeIdRef.current ?? null,
        });
        if (!uploaded) {
          throw new Error("Could not share the workflow with the assistant.");
        }
        appliedRevisionRef.current = uploaded.revision;
        setCanvas(clearAiChanges(nodesRef.current), edgesRef.current);

        try {
          await chatSend(outgoing);
        } catch (sendError) {
          // A resumed conversation can be gone on the server (finalized, expired). The
          // service clears it when that happens; start a fresh one and send again.
          if (chatRef.current?.getConversationId?.()) throw sendError;
          await startConversationIfNeeded();
          const freshId = chatRef.current?.getConversationId?.();
          if (!freshId) throw sendError;
          await putBuilderDraft(freshId, {
            ...snapshot(),
            selected_node_id: focusNodeIds[0] ?? selectedNodeIdRef.current ?? null,
          });
          addAgentMessage({
            text: "Our previous conversation had expired, so I started a new one. The workflow on the canvas is unchanged.",
          });
          await chatSend(outgoing);
        }
      } catch (err) {
        suppressWelcomeRef.current = false;
        setIsThinking(false);
        updateLiveTurn(null);
        const errMsg =
          err instanceof Error ? err.message : "Failed to send message.";
        addAgentMessage({ text: errMsg });
      }
    },
    // chatRef is a stable ref from useChatService
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [chatSend, startConversationIfNeeded, updateMessages, addAgentMessage, snapshot, setCanvas, beginTurn, updateLiveTurn]
  );

  /**
   * Answer a question the assistant asked (one of its options, or the person's own
   * words): the answer is recorded on the question and sent as the next message.
   */
  const answerQuestion = useCallback(
    (messageId: string, answer: string) => {
      const trimmed = answer.trim();
      if (!trimmed) return;
      updateMessages((prev) => prev.map((msg) => (msg.id === messageId ? { ...msg, answer: trimmed } : msg)));
      void sendMessage(trimmed);
    },
    [sendMessage, updateMessages]
  );

  /**
   * A focused action on the canvas as it is: one server call, no builder turn.
   * The result is shown as an assistant message; proposals wait for approval.
   */
  const runAssist = useCallback(
    async (action: AssistAction, nodeIds: string[] = [], instruction = "", label?: string) => {
      const names = nodeIds
        .map((id) => nodesRef.current.find((n) => n.id === id)?.data?.name)
        .filter((n): n is string => typeof n === "string");
      const messageId = uuidv4();
      updateMessages((prev) => [
        ...prev,
        {
          id: messageId,
          speaker: "customer",
          text: label ?? `${ACTION_LABELS[action]}${names.length ? ` "${names.join('", "')}"` : ""}`,
        },
      ]);
      beginTurn(messageId);
      setIsThinking(true);
      updateLiveTurn({ ...newLiveTurn(), steps: [{ id: "assist", kind: ACTION_STEP_KINDS[action], text: ACTION_STEPS[action], done: false }] });
      try {
        const result = await runAssistAction(snapshot(), action, nodeIds, instruction);
        if (!result) throw new Error("The assistant did not answer.");
        if (result.kind === "text") {
          addAgentMessage({ text: result.text });
        } else if (result.kind === "messages") {
          addAgentMessage({
            text: result.messages.length
              ? "Try these messages; click one to run it from the Executions tab."
              : "I could not come up with test messages for this workflow.",
            suggestions: result.messages,
          });
        } else if (result.kind === "proposals") {
          addAgentMessage({
            text: result.proposals.length
              ? `${result.proposals.length === 1 ? "One change" : `${result.proposals.length} changes`} to consider. Apply the ones you want.`
              : "Nothing worth changing here.",
            proposals: result.proposals,
          });
        } else {
          const problems = result.findings.filter((f) => f.severity !== "setup");
          addAgentMessage({
            text: problems.length
              ? `${problems.length} thing${problems.length === 1 ? "" : "s"} to look at.`
              : "No problems found. Only the setup items below remain, if any.",
            findings: result.findings,
          });
        }
      } catch (err) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        addAgentMessage({ text: detail || (err instanceof Error ? err.message : "That did not work.") });
      } finally {
        setIsThinking(false);
        updateLiveTurn(null);
      }
    },
    [addAgentMessage, snapshot, updateMessages, beginTurn, updateLiveTurn]
  );

  /**
   * Add one step after a given output of a step, from a sentence ("Add with AI"
   * on the canvas). One model call designs it; it lands at once, highlighted,
   * and can be undone like any other change.
   */
  const addStepWithAi = useCallback(
    async (sourceNodeId: string, sourceHandle: string, handleLabel: string, instruction: string) => {
      const trimmed = instruction.trim();
      if (!trimmed) return;
      const sourceName = (nodesRef.current.find((n) => n.id === sourceNodeId)?.data?.name as string | undefined) ?? "this step";
      const messageId = uuidv4();
      updateMessages((prev) => [
        ...prev,
        { id: messageId, speaker: "customer", text: `Add a step after "${sourceName}" (${handleLabel}): ${trimmed}` },
      ]);
      beginTurn(messageId);
      setIsThinking(true);
      updateLiveTurn({ ...newLiveTurn(), steps: [{ id: "design", kind: "edit", text: `Designing a step after “${sourceName}”`, done: false }] });
      try {
        const designed = await runAssistAction(snapshot(), "add_step", [sourceNodeId], trimmed, sourceHandle);
        if (!designed || designed.kind !== "proposals" || designed.proposals.length === 0) {
          throw new Error("I could not work out a step for that. Try describing it differently.");
        }
        const proposal = designed.proposals[0];
        updateLiveTurn({
          ...(liveTurnRef.current ?? newLiveTurn()),
          steps: [
            { id: "design", kind: "edit", text: `Designing a step after “${sourceName}”`, done: true },
            { id: "apply", kind: "edit", text: `Adding ${proposal.title.replace(/^Add /, "")}`, done: false },
          ],
        });
        const result = await applyBuilderOperations(snapshot(), proposal.operations);
        if (!result) throw new Error("The step could not be added.");
        applyDraftToCanvas(result);
        const failed = result.report.includes("FAILED");
        addAgentMessage({
          text: failed
            ? `The step could not be added as designed:\n${result.report}`
            : `${proposal.title.replace(/^Add /, "Added ")} after "${sourceName}". Open it to adjust the details, or tell me what to change.`,
          changes: result.changes,
          issues: reportableIssues(result),
          ...settleLiveTurn(liveTurnRef.current ?? newLiveTurn()),
        });
      } catch (err) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        addAgentMessage({ text: detail || (err instanceof Error ? err.message : "The step could not be added.") });
      } finally {
        setIsThinking(false);
        updateLiveTurn(null);
      }
    },
    [addAgentMessage, applyDraftToCanvas, beginTurn, snapshot, updateLiveTurn, updateMessages]
  );

  /** Apply one approved proposal; the result is highlighted and can be undone. */
  const applyProposal = useCallback(
    async (messageId: string, proposal: AssistProposal) => {
      setIsThinking(true);
      try {
        const result = await applyBuilderOperations(snapshot(), proposal.operations);
        if (!result) throw new Error("The change could not be applied.");
        applyDraftToCanvas(result);
        const failed = result.report.includes("FAILED");
        updateMessages((prev) =>
          prev.map((msg) =>
            msg.id === messageId
              ? { ...msg, proposals: msg.proposals?.filter((p) => p !== proposal) }
              : msg
          )
        );
        addAgentMessage({
          text: failed
            ? `"${proposal.title}" could only be applied in part:\n${result.report}`
            : `Applied: ${proposal.title}.`,
          changes: result.changes,
          issues: reportableIssues(result),
        });
      } catch (err) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        addAgentMessage({ text: detail || (err instanceof Error ? err.message : "The change could not be applied.") });
      } finally {
        setIsThinking(false);
      }
    },
    [addAgentMessage, applyDraftToCanvas, snapshot, updateMessages]
  );

  /** Thumbs up or down on a reply, kept with the chat. */
  const reactToMessage = useCallback(
    (messageId: string, reaction: "up" | "down" | null) => {
      updateMessages((prev) =>
        prev.map((msg) => (msg.id === messageId ? { ...msg, reaction: reaction ?? undefined } : msg))
      );
    },
    [updateMessages]
  );

  const clearHistory = useCallback(() => {
    updateMessages(() => []);
    appliedRevisionRef.current = 0;
    beforeChangeRef.current = null;
    turnSnapshotsRef.current.clear();
    setPendingChange(null);
    forgetChat(workflowScopeId);
    resetConversation();
  }, [resetConversation, updateMessages, workflowScopeId]);

  return {
    messages,
    isThinking,
    liveTurn,
    sendMessage,
    answerQuestion,
    reactToMessage,
    runAssist,
    addStepWithAi,
    applyProposal,
    pendingChange,
    keepChanges,
    undoChanges,
    undoTurn,
    simulateActions,
    setSimulateActions,
    clearHistory,
    hasConfig,
    /** The server conversation behind this chat, once the first message was sent. */
    getConversationId: () => chatRef.current?.getConversationId?.() ?? null,
  };
}

const ACTION_LABELS: Record<AssistAction, string> = {
  explain_node: "Explain",
  explain_group: "Explain",
  describe_workflow: "Describe this workflow",
  explain_step: "Why did this run like that?",
  suggest_tests: "Suggest test messages",
  review: "Review the workflow",
  improve_prompt: "Improve the prompt of",
  generate_code: "Generate",
  optimize: "Optimize",
  add_step: "Add a step",
};

// What the trail shows while a focused action (one model call) is running.
const ACTION_STEPS: Record<AssistAction, string> = {
  explain_node: "Reading the step",
  explain_group: "Reading the steps",
  describe_workflow: "Reading the workflow",
  explain_step: "Reading your last test run",
  suggest_tests: "Thinking of test messages",
  review: "Checking the workflow",
  improve_prompt: "Rewriting the prompt",
  generate_code: "Writing the code",
  optimize: "Looking for improvements",
  add_step: "Designing the step",
};

const ACTION_STEP_KINDS: Record<AssistAction, string> = {
  explain_node: "read",
  explain_group: "read",
  describe_workflow: "read",
  explain_step: "test",
  suggest_tests: "test",
  review: "finalize",
  improve_prompt: "edit",
  generate_code: "edit",
  optimize: "lookup",
  add_step: "edit",
};
