import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type AgentWelcomeData, type ChatMessage, type StreamEvent } from "genassist-chat-react";
import { type RegistrationStatus } from "@/context/RoutesContext";
import { useChatService } from "@/hooks/useChatService";
import { getBuilderDraftStatus, type BuilderQuestion } from "@/services/workflowBuilder";
import {
  applyLiveStreamEvent,
  newLiveTurn,
  settleLiveTurn,
  type AssistantStep,
  type LiveTurn,
} from "@/views/AIAgents/Workflows/utils/assistantDraft";
import {
  extractWorkflowDraftFromText,
  hasWorkflowReadySignal,
  stripWorkflowTags,
  type WorkflowDraft,
} from "@/views/Onboarding/utils/extractWorkflowDraft";

const RESPONSE_TIMEOUT_MS = 180_000;

export interface OnboardingMessage {
  role: "user" | "agent";
  text: string;
  /** What the builder did before this reply (narrated steps, thoughts). */
  steps?: AssistantStep[];
  workedMs?: number;
  /** The reply was shown as it streamed, so it needs no reveal animation. */
  streamed?: boolean;
  /** A question the builder asked, with answers to click. */
  question?: BuilderQuestion;
  answer?: string;
  reaction?: "up" | "down";
}

export const useOnboardingChat = ({ registrationStatus }: { registrationStatus: RegistrationStatus }) => {
  const [error, setError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<string>("");
  const [agentReply, setAgentReply] = useState<string | null>(null);
  const [messages, setMessages] = useState<OnboardingMessage[]>([]);
  const [workflowDraft, setWorkflowDraft] = useState<WorkflowDraft | null>(null);
  const workflowDraftRef = useRef<WorkflowDraft | null>(null);
  const [isWorkflowReady, setIsWorkflowReady] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  // The builder's work in progress: narrated steps and the reply as it streams in.
  const [liveTurn, setLiveTurn] = useState<LiveTurn | null>(null);
  const liveTurnRef = useRef<LiveTurn | null>(null);
  const updateLiveTurn = useCallback((turn: LiveTurn | null) => {
    liveTurnRef.current = turn;
    setLiveTurn(turn);
  }, []);
  const [thinkingPhrases, setThinkingPhrases] = useState<string[]>([]);
  const [thinkingDelayMs, setThinkingDelayMs] = useState<number>(1000);
  const [thinkingIndex, setThinkingIndex] = useState(0);
  const [hasUserStartedChat, setHasUserStartedChat] = useState(false);
  const [welcomeTitle, setWelcomeTitle] = useState<string | null>(null);
  const [welcomeMessage, setWelcomeMessage] = useState<string | null>(null);
  const [welcomeFaqs, setWelcomeFaqs] = useState<string[]>([]);
  const hasUserAskedRef = useRef(false);
  const hasUserStartedChatRef = useRef(false);
  const thinkingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const getConversationIdRef = useRef<() => string | null>(() => null);

  // The builder agent keeps the workflow in a server-side draft; ask the server
  // whether it is ready instead of looking for it in the reply text.
  const refreshDraftFromServer = useCallback(async () => {
    const conversationId = getConversationIdRef.current();
    const baseUrl = (import.meta.env.VITE_ONBOARDING_API_URL as string) || "";
    const apiKey = (import.meta.env.VITE_ONBOARDING_CHAT_APIKEY as string) || "";
    if (!conversationId || !baseUrl || !apiKey) return;
    try {
      const status = await getBuilderDraftStatus(conversationId, {
        baseUrl,
        apiKey,
        tenant: localStorage.getItem("tenant_id") || undefined,
      });
      if (status?.question) {
        const question = status.question;
        setMessages((prev) => {
          const last = prev.length - 1;
          return prev.map((msg, index) => (index === last && msg.role === "agent" ? { ...msg, question } : msg));
        });
      }
      if (!status?.spec?.workflow?.length) return;
      // conversation_id lets the post-login step create the workflow from the stored draft.
      const draft: WorkflowDraft = { ...status.spec, conversation_id: conversationId };
      workflowDraftRef.current = draft;
      setWorkflowDraft(draft);
      if (status.ready) setIsWorkflowReady(true);
    } catch {
      // The chat keeps working without the preview; the next reply retries.
    }
  }, []);

  // ── Message handler ──
  const handleMessage = useCallback((message: ChatMessage) => {
    if (!hasUserAskedRef.current) return;
    if (message.speaker !== "customer") {
      setIsThinking(false);
      if (thinkingTimeoutRef.current) {
        clearTimeout(thinkingTimeoutRef.current);
        thinkingTimeoutRef.current = null;
      }
    }
    if (message.speaker === "agent") {
      const rawText = message.text;
      // What the builder did on the way to this reply stays with it.
      const turn = liveTurnRef.current;
      const work = turn ? settleLiveTurn(turn) : {};
      const streamed = Boolean(turn && turn.text.trim());
      updateLiveTurn(null);

      // Fallback for a builder agent that still writes the workflow into its reply.
      const extracted = extractWorkflowDraftFromText(rawText);
      if (extracted) {
        workflowDraftRef.current = extracted.parsed;
        setWorkflowDraft(extracted.parsed);
        if (extracted.isReady) {
          setIsWorkflowReady(true);
        }
      } else if (hasWorkflowReadySignal(rawText) && workflowDraftRef.current) {
        setIsWorkflowReady(true);
      }

      const displayText = stripWorkflowTags(rawText);
      setAgentReply(displayText);
      setMessages((prev) => [...prev, { role: "agent", text: displayText, ...work, streamed }]);
      // After the message is in place, so a question lands on it.
      void refreshDraftFromServer();
    }
  }, [refreshDraftFromServer, updateLiveTurn]);

  const handleStream = useCallback(
    (event: StreamEvent) => {
      if (!hasUserAskedRef.current) return;
      updateLiveTurn(applyLiveStreamEvent(liveTurnRef.current ?? newLiveTurn(), event));
      // Progress means the turn is alive: push the safety timeout back.
      if (thinkingTimeoutRef.current) {
        clearTimeout(thinkingTimeoutRef.current);
        thinkingTimeoutRef.current = setTimeout(() => {
          setIsThinking(false);
          updateLiveTurn(null);
          setError("Response timed out. Please try again.");
          thinkingTimeoutRef.current = null;
        }, RESPONSE_TIMEOUT_MS);
      }
    },
    [updateLiveTurn]
  );

  // ── Welcome data handler ──
  const handleWelcomeData = useCallback((data: AgentWelcomeData) => {
    if (hasUserStartedChatRef.current) return;
    setWelcomeTitle(data?.title ?? null);
    setWelcomeMessage(data?.message ?? null);
    const faqOptions = Array.isArray(data?.possibleQueries)
      ? data.possibleQueries.filter((q) => typeof q === "string" && q.trim().length > 0)
      : [];
    setWelcomeFaqs(faqOptions);
  }, []);

  const {
    sendMessage: chatSend,
    hasConfig,
    chatRef,
    startConversationIfNeeded,
  } = useChatService({
    onMessage: handleMessage,
    onStream: handleStream,
    onWelcomeData: handleWelcomeData,
  });
  getConversationIdRef.current = () => chatRef.current?.getConversationId?.() ?? null;

  // Helper: read thinking config from the ChatService and update state
  const applyThinkingConfig = useCallback(() => {
    const cfg = chatRef.current?.getThinkingConfig?.();
    if (!cfg) return;
    if (Array.isArray(cfg.phrases) && cfg.phrases.length) {
      setThinkingPhrases(cfg.phrases);
    }
    if (typeof cfg.delayMs === "number") {
      setThinkingDelayMs(Math.max(250, cfg.delayMs));
    }
  }, [chatRef]);

  // ── Read thinking config once connected (static defaults) ──
  useEffect(() => {
    if (!hasConfig || !chatRef.current) return;
    applyThinkingConfig();
  }, [hasConfig, chatRef, applyThinkingConfig]);

  // ── Cleanup thinking timeout on unmount ──
  useEffect(() => {
    return () => {
      if (thinkingTimeoutRef.current) {
        clearTimeout(thinkingTimeoutRef.current);
      }
    };
  }, []);

  // ── Auto-start conversation when ready ──
  // Re-read thinking config after startConversation, since the server
  // may provide config data (phrases, delay) during the handshake.
  useEffect(() => {
    if (!hasConfig) return;
    if (chatRef.current?.getConversationId?.()) return;

    startConversationIfNeeded()
      .then(() => applyThinkingConfig())
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Unable to start onboarding chat.";
        setError(message);
      });
  }, [hasConfig, startConversationIfNeeded, chatRef, registrationStatus, applyThinkingConfig]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      if (!hasConfig) {
        setError("Add VITE_ONBOARDING_CHAT_APIKEY and VITE_ONBOARDING_API_URL to use onboarding chat.");
        return;
      }

      if (!chatRef.current) {
        setError("Chat service not ready yet.");
        return;
      }

      setError(null);
      setHasUserStartedChat(true);
      hasUserStartedChatRef.current = true;
      setWelcomeMessage(null);
      setWelcomeFaqs([]);
      setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
      setPrompt("");
      setIsSending(true);
      hasUserAskedRef.current = true;
      setIsThinking(true);
      updateLiveTurn(newLiveTurn());
      setThinkingIndex(0);

      // Safety timeout — building a workflow takes many steps, so allow a few minutes
      thinkingTimeoutRef.current = setTimeout(() => {
        setIsThinking(false);
        setError("Response timed out. Please try again.");
        thinkingTimeoutRef.current = null;
      }, RESPONSE_TIMEOUT_MS);

      try {
        await chatSend(trimmed);
      } catch (err: unknown) {
        if (thinkingTimeoutRef.current) {
          clearTimeout(thinkingTimeoutRef.current);
          thinkingTimeoutRef.current = null;
        }
        const message = err instanceof Error ? err.message : "Unable to send message.";
        setError(message);
        setIsThinking(false);
        updateLiveTurn(null);
      } finally {
        setIsSending(false);
      }
    },
    [hasConfig, chatSend, chatRef, updateLiveTurn],
  );

  /** Answer a question the builder asked: recorded on the question, sent as the next message. */
  const answerQuestion = useCallback(
    (messageIndex: number, answer: string) => {
      const trimmed = answer.trim();
      if (!trimmed) return;
      setMessages((prev) => prev.map((msg, index) => (index === messageIndex ? { ...msg, answer: trimmed } : msg)));
      void sendMessage(trimmed);
    },
    [sendMessage]
  );

  const reactToMessage = useCallback((messageIndex: number, reaction: "up" | "down" | null) => {
    setMessages((prev) =>
      prev.map((msg, index) => (index === messageIndex ? { ...msg, reaction: reaction ?? undefined } : msg))
    );
  }, []);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      await sendMessage(prompt);
    },
    [prompt, sendMessage],
  );

  const sendQuickAction = useCallback(
    async (message: string) => {
      if (isSending) return;
      setPrompt(message);
      await sendMessage(message);
    },
    [isSending, sendMessage],
  );

  useEffect(() => {
    if (!isThinking) return;
    const timer = setInterval(() => {
      setThinkingIndex((prev) => (prev + 1) % (thinkingPhrases.length || 1));
    }, Math.max(500, thinkingDelayMs));
    return () => clearInterval(timer);
  }, [isThinking, thinkingDelayMs, thinkingPhrases.length]);

  const subtitleText = useMemo(() => {
    if (agentReply) return agentReply;
    if (isThinking) return thinkingPhrases[thinkingIndex] || "Thinking\u2026";
    if (!hasUserStartedChat) return welcomeMessage || "Now let's create your first agent together.";
    return "Now let's create your first agent together.";
  }, [agentReply, isThinking, thinkingPhrases, thinkingIndex, hasUserStartedChat, welcomeMessage]);

  const titleText = welcomeTitle || "What do you want to automate?";

  return {
    prompt,
    setPrompt,
    agentReply,
    messages,
    isThinking,
    liveTurn,
    sendMessage,
    answerQuestion,
    reactToMessage,
    subtitleText,
    titleText,
    welcomeFaqs,
    hasUserStartedChat,
    isSending,
    error,
    hasConfig,
    handleSubmit,
    sendQuickAction,
    workflowDraft,
    isWorkflowReady,
  };
};
