import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatService, type AgentWelcomeData, type ChatMessage } from "genassist-chat-react";
import { type RegistrationStatus } from "@/context/RoutesContext";  

export const useOnboardingChat = ({ registrationStatus }: { registrationStatus: RegistrationStatus }) => {
  const [error, setError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<string>("");
  const [agentReply, setAgentReply] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingPhrases, setThinkingPhrases] = useState<string[]>([]);
  const [thinkingDelayMs, setThinkingDelayMs] = useState<number>(1000);
  const [thinkingIndex, setThinkingIndex] = useState(0);
  const [isChatReady, setIsChatReady] = useState(false);
  const [hasUserStartedChat, setHasUserStartedChat] = useState(false);
  const [welcomeTitle, setWelcomeTitle] = useState<string | null>(null);
  const [welcomeMessage, setWelcomeMessage] = useState<string | null>(null);
  const [welcomeFaqs, setWelcomeFaqs] = useState<string[]>([]);
  const hasUserAskedRef = useRef(false);
  const isMountedRef = useRef(true);
  const isStartingConversationRef = useRef(false);
  const hasUserStartedChatRef = useRef(false);

  const onboardingBaseUrl = (import.meta.env.VITE_ONBOARDING_API_URL as string) || "";
  const onboardingApiKey = (import.meta.env.VITE_ONBOARDING_CHAT_APIKEY as string) || "";
  const tenant = (localStorage.getItem("tenant_id") as string | null) || undefined;
  const chatRef = useRef<ChatService | null>(null);

  const hasConfig = useMemo(() => Boolean(onboardingBaseUrl && onboardingApiKey), [onboardingApiKey, onboardingBaseUrl]);

  useEffect(() => {
    if (!hasConfig || !onboardingBaseUrl) return;

    const chat = new ChatService(onboardingBaseUrl, onboardingApiKey, undefined, tenant);
    chatRef.current = chat;
    chat.resetConversation();
    setIsChatReady(true);

    const handleWelcomeData = (data: AgentWelcomeData) => {
      if (hasUserStartedChatRef.current) return;
      setWelcomeTitle(data?.title ?? null);
      setWelcomeMessage(data?.message ?? null);
      const faqOptions = Array.isArray(data?.possibleQueries)
        ? data.possibleQueries.filter((q) => typeof q === "string" && q.trim().length > 0)
        : [];
      setWelcomeFaqs(faqOptions);
    };

    chat.setWelcomeDataHandler(handleWelcomeData);

    const cfg = chat.getThinkingConfig?.();
    if (cfg) {
      if (Array.isArray(cfg.phrases) && cfg.phrases.length) {
        setThinkingPhrases(cfg.phrases);
      }
      if (typeof cfg.delayMs === "number") {
        setThinkingDelayMs(Math.max(250, cfg.delayMs));
      }
    }

    chat.setMessageHandler((message: ChatMessage) => {
      if (!hasUserAskedRef.current) return;
      if (message.speaker !== "customer") {
        setIsThinking(false);
      }
      if (message.speaker === "agent") {
        setAgentReply(message.text);
      }
    });

    return () => {
      if (isMountedRef.current) {
        setIsChatReady(false);
      }
      chat.setWelcomeDataHandler(null);
      chat.disconnect();
      chatRef.current = null;
    };
  }, [onboardingApiKey, onboardingBaseUrl, hasConfig, tenant]);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const startConversationIfNeeded = useCallback(async () => {
    const chat = chatRef.current;
    if (!chat || isStartingConversationRef.current) return;

    const activeConversationId = chat.getConversationId?.();
    if (activeConversationId) {
      if (!conversationId) {
        setConversationId(activeConversationId);
      }
      return;
    }

    if (conversationId) return;
    isStartingConversationRef.current = true;
    try {
      const id = await chat.startConversation(undefined);
      if (!isMountedRef.current) return;
      setConversationId(id);
      const cfg = chat.getThinkingConfig?.();
      if (cfg) {
        if (Array.isArray(cfg.phrases) && cfg.phrases.length) {
          setThinkingPhrases(cfg.phrases);
        }
        if (typeof cfg.delayMs === "number") {
          setThinkingDelayMs(Math.max(250, cfg.delayMs));
        }
      }
    } finally {
      isStartingConversationRef.current = false;
    }
  }, [conversationId]);

  useEffect(() => {
    if (!hasConfig || !isChatReady) return;
    if (chatRef.current?.getConversationId?.()) return;

    // if the registration status is existing, skip the conversation
    if (registrationStatus === "existing") return;

    startConversationIfNeeded().catch((err: unknown) => {
      if (!isMountedRef.current) return;
      const message = err instanceof Error ? err.message : "Unable to start onboarding chat.";
      setError(message);
    });
  }, [hasConfig, isChatReady, startConversationIfNeeded, registrationStatus]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      if (!hasConfig) {
        setError("Add VITE_GENASSIST_CHAT_APIKEY and API URL to use onboarding chat.");
        return;
      }

      const chat = chatRef.current;
      if (!chat) {
        setError("Chat service not ready yet.");
        return;
      }

      setError(null);
      setHasUserStartedChat(true);
      hasUserStartedChatRef.current = true;
      setWelcomeMessage(null);
      setWelcomeFaqs([]);
      setIsSending(true);
      hasUserAskedRef.current = true;
      setIsThinking(true);
      setThinkingIndex(0);

      try {
        await startConversationIfNeeded();
        await chat.sendMessage(trimmed);
        setPrompt("");
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Unable to send message.";
        setError(message);
        setIsThinking(false);
      } finally {
        setIsSending(false);
      }
    },
    [hasConfig, startConversationIfNeeded],
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

  const subtitleText =
    agentReply ||
    (isThinking
      ? thinkingPhrases[thinkingIndex] || "Thinking…"
      : !hasUserStartedChat
        ? welcomeMessage || "Now let's create your first agent together."
        : "Now let's create your first agent together.");

  const titleText = welcomeTitle || "What would you like your agent to do?";

  return {
    prompt,
    setPrompt,
    agentReply,
    subtitleText,
    titleText,
    welcomeFaqs,
    hasUserStartedChat,
    isSending,
    error,
    hasConfig,
    handleSubmit,
    sendQuickAction,
  };
};