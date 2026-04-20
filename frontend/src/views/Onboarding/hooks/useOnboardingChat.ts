import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type AgentWelcomeData, type ChatMessage } from "genassist-chat-react";
import { type RegistrationStatus } from "@/context/RoutesContext";
import { useChatService } from "@/hooks/useChatService";
import {
  extractWorkflowDraftFromText,
  hasWorkflowReadySignal,
  stripWorkflowTags,
  type WorkflowDraft,
} from "@/views/Onboarding/utils/extractWorkflowDraft";

export interface OnboardingMessage {
  role: "user" | "agent";
  text: string;
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

      // Extract progressive workflow draft if present
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
      setMessages((prev) => [...prev, { role: "agent", text: displayText }]);
    }
  }, []);

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
    onWelcomeData: handleWelcomeData,
  });

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
        setError("Add VITE_GENASSIST_CHAT_APIKEY and API URL to use onboarding chat.");
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
      setThinkingIndex(0);

      // Safety timeout — clear thinking state if no response within 60s
      thinkingTimeoutRef.current = setTimeout(() => {
        setIsThinking(false);
        setError("Response timed out. Please try again.");
        thinkingTimeoutRef.current = null;
      }, 60_000);

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
      } finally {
        setIsSending(false);
      }
    },
    [hasConfig, chatSend, chatRef],
  );

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

  const titleText = welcomeTitle || "What would you like your agent to do?";

  return {
    prompt,
    setPrompt,
    agentReply,
    messages,
    isThinking,
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
