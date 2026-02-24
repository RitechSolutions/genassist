import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { ChatService } from "../services/chatService";
import {
  ChatMessage,
  Attachment,
  MessageFeedback,
  InProgressPollMessage,
} from "../types";

export interface UseChatProps {
  baseUrl: string;
  apiKey: string;
  tenant?: string | undefined;
  metadata?: Record<string, any>;
  //  If false, the chat will run in HTTP-only mode (no WebSocket connection).
  useWs?: boolean;
  usePoll?: boolean;
  language?: string;
  onError?: (error: Error) => void;
  onTakeover?: () => void;
  onFinalize?: () => void;
  serverUnavailableMessage?: string; // Custom message when server is down
  serverUnavailableContactUrl?: string; // Optional URL for contact/support
  serverUnavailableContactLabel?: string; // Label for the contact link
  onConfigLoaded?: (props: { chatInputMetadata?: Record<string, any> }) => void; // Callback for when the chat input metadata is loaded
}

const DEFAULT_SERVER_UNAVAILABLE_MESSAGE =
  "The service is temporarily unavailable. Please try again later.";
const DEFAULT_SERVER_UNAVAILABLE_CONTACT_LABEL = "Contact support";

function isNetworkOrServerError(error: any): boolean {
  // No response = network error
  if (!error.response) {
    const code = error?.code;
    if (
      code === "ERR_NETWORK" ||
      code === "ECONNREFUSED" ||
      code === "ETIMEDOUT" ||
      code === "ERR_CONNECTION_REFUSED"
    )
      return true;
    return true; // any request error without response is treated as server/network issue
  }
  const status = error.response?.status;
  return typeof status === "number" && status >= 500;
}

export const useChat = ({
  baseUrl,
  apiKey,
  tenant,
  metadata,
  useWs = true,
  usePoll = false,
  language,
  onError,
  onTakeover,
  onFinalize,
  serverUnavailableMessage,
  serverUnavailableContactUrl,
  serverUnavailableContactLabel,
  onConfigLoaded,
}: UseChatProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [preloadedAttachments, setPreloadedAttachments] = useState<
    Attachment[]
  >([]);
  const [connectionState, setConnectionState] = useState<
    "connecting" | "connected" | "disconnected"
  >("disconnected");
  const [isAgentTyping, setIsAgentTyping] = useState<boolean>(false);
  const chatServiceRef = useRef<ChatService | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [possibleQueries, setPossibleQueries] = useState<string[]>([]);
  const [welcomeTitle, setWelcomeTitle] = useState<string | null>(null);
  const [welcomeImageUrl, setWelcomeImageUrl] = useState<string | null>(null);
  const [welcomeMessage, setWelcomeMessage] = useState<string | null>(null);
  const [thinkingPhrases, setThinkingPhrases] = useState<string[]>([]);
  const [thinkingDelayMs, setThinkingDelayMs] = useState<number>(1000);
  const [chatInputMetadata, setChatInputMetadata] = useState<
    Record<string, unknown>
  >({});
  const [isTakenOver, setIsTakenOver] = useState<boolean>(false);
  const [isFinalized, setIsFinalized] = useState<boolean>(false);
  const [isPolling, setIsPolling] = useState<boolean>(false);

  // Scoped messages key for apiKey, conversatioId
  const buildMessagesKey = useCallback(
    (apiKeyVal: string, convId: string | null) => {
      if (!convId) return null;
      return `genassist_conversation_messages:${apiKeyVal}:${convId}`;
    },
    [],
  );

  const validateMessages = useCallback(
    (messages: ChatMessage[]) => {
      const hasTakeOverMsg = messages.some((m) => m?.type === "takeover");
      const hasFinalizedMsg = messages.some((m) => m?.type === "finalized");
      setIsTakenOver(hasTakeOverMsg);
      setIsFinalized(hasFinalizedMsg);
    },
    [setIsTakenOver, setIsFinalized],
  );

  // Check if an error is a token expiration error (401 + "Token has expired.")
  const isTokenExpiredError = useCallback((error: any): boolean => {
    return !!(
      error?.response?.status === 401 &&
      error?.response?.data &&
      (error.response.data.error === "Token has expired." ||
        error.response.data.message === "Token has expired." ||
        (typeof error.response.data === "string" &&
          error.response.data.includes("Token has expired")))
    );
  }, []);

  // Reset conversation state to initial (e.g. after token expiration)
  const resetToInitialState = useCallback(() => {
    setConversationId(null);
    setIsFinalized(false);
    setIsTakenOver(false);
    setConnectionState("disconnected");
    setWelcomeTitle(null);
    setWelcomeImageUrl(null);
    setWelcomeMessage(null);
    setPossibleQueries([]);
    setThinkingPhrases([]);
    setThinkingDelayMs(1000);
    setChatInputMetadata({});
    setMessages([]);
    lastServerCreateTimeRef.current = 0;
    const key = buildMessagesKey(apiKey, conversationId);
    if (key) {
      try {
        localStorage.removeItem(key);
      } catch (e) {
        // ignore
      }
    }
  }, [apiKey, conversationId, buildMessagesKey]);

  // Deep compare metadata to prevent unnecessary re-initializations
  // Only re-initialize if metadata actually changes (by value, not reference)
  const metadataString = useMemo(
    () => JSON.stringify(metadata || {}),
    [metadata],
  );
  const metadataRef = useRef<string>(metadataString);
  const prevBaseUrlRef = useRef<string>(baseUrl);
  const prevApiKeyRef = useRef<string>(apiKey);
  const prevTenantRef = useRef<string | undefined>(tenant);
  const prevUseWsRef = useRef<boolean>(useWs);
  const prevUsePollRef = useRef<boolean>(usePoll);

  // Heartbeat polling state (when WebSocket is disabled)
  const heartbeatFailureCountRef = useRef<number>(0);
  const heartbeatIntervalRef = useRef<number>(0);
  const lastServerCreateTimeRef = useRef<number>(0);
  // Refs so we only run takeover/finalized once per conversation (avoid stale isTakenOver/isFinalized in poll closure)
  const takeoverProcessedRef = useRef<boolean>(false);
  const finalizedProcessedRef = useRef<boolean>(false);

  // Store callbacks in refs so they don't trigger re-initialization
  const onErrorRef = useRef(onError);
  const onTakeoverRef = useRef(onTakeover);
  const onFinalizeRef = useRef(onFinalize);
  const onConfigLoadedRef = useRef(onConfigLoaded);

  // Update callback refs when they change
  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    onTakeoverRef.current = onTakeover;
  }, [onTakeover]);

  useEffect(() => {
    onFinalizeRef.current = onFinalize;
  }, [onFinalize]);

  useEffect(() => {
    onConfigLoadedRef.current = onConfigLoaded;
  }, [onConfigLoaded]);

  // Initialize chat service - only when baseUrl, apiKey, tenant, useWs, or metadata actually change
  useEffect(() => {
    const metadataChanged = metadataRef.current !== metadataString;
    const baseUrlChanged = prevBaseUrlRef.current !== baseUrl;
    const apiKeyChanged = prevApiKeyRef.current !== apiKey;
    const tenantChanged = prevTenantRef.current !== tenant;
    const useWsChanged = prevUseWsRef.current !== useWs;
    const usePollChanged = prevUsePollRef.current !== usePoll;
    // Only re-initialize for connection-related changes, NOT for metadata changes
    const needsReinit =
      !chatServiceRef.current ||
      baseUrlChanged ||
      apiKeyChanged ||
      tenantChanged ||
      useWsChanged;

    if (needsReinit) {
      // Update refs
      if (baseUrlChanged) prevBaseUrlRef.current = baseUrl;
      if (apiKeyChanged) prevApiKeyRef.current = apiKey;
      if (tenantChanged) prevTenantRef.current = tenant;
      if (useWsChanged) prevUseWsRef.current = useWs;
      if (usePollChanged) prevUsePollRef.current = usePoll;
      if (metadataChanged) metadataRef.current = metadataString;

      // Clean up existing service if it exists
      if (chatServiceRef.current) {
        chatServiceRef.current.setConnectionStateHandler(() => {});
        chatServiceRef.current.disconnect();
        chatServiceRef.current.setWelcomeDataHandler(null);
      }

      chatServiceRef.current = new ChatService(
        baseUrl,
        apiKey,
        metadata,
        tenant,
        language,
        useWs,
        usePoll,
      );

      // Set up handlers
      chatServiceRef.current.setMessageHandler((message: ChatMessage) => {
        const normalizedMessage: ChatMessage = {
          ...message,
          create_time:
            !message.create_time || isNaN(message.create_time)
              ? Math.floor(Date.now() / 1000)
              : message.create_time,
        };

        // Track latest create_time we've seen from server/websocket (in seconds)
        if (normalizedMessage.create_time) {
          if (
            normalizedMessage.create_time >
            (lastServerCreateTimeRef.current || 0)
          ) {
            lastServerCreateTimeRef.current = normalizedMessage.create_time;
          }
        }

        setMessages((prevMessages) => {
          // Avoid adding duplicate messages with same message_id and type
          if (normalizedMessage.message_id && normalizedMessage.type) {
            const exists = prevMessages.some(
              (m) =>
                m.message_id === normalizedMessage.message_id &&
                m.type === normalizedMessage.type,
            );
            if (exists) {
              return prevMessages;
            }
          }
          return [...prevMessages, normalizedMessage];
        });
        // Stop typing animation when agent or system message arrives
        if (
          normalizedMessage.speaker === "agent" ||
          normalizedMessage.speaker === "special"
        ) {
          setIsAgentTyping(false);
        }
      });

      chatServiceRef.current.setTakeoverHandler(() => {
        setIsTakenOver(true);
        setIsAgentTyping(false);
        if (onTakeoverRef.current) {
          onTakeoverRef.current();
        }
      });

      chatServiceRef.current.setFinalizedHandler(() => {
        setIsFinalized(true);
        setIsAgentTyping(false);
        if (onFinalizeRef.current) {
          onFinalizeRef.current();
        }
      });

      chatServiceRef.current.setConnectionStateHandler((state) => {
        setConnectionState(state);
        if (state !== "connected") {
          setIsAgentTyping(false);
        }
      });

      chatServiceRef.current.setWelcomeDataHandler((data) => {
        setWelcomeTitle(data.title ?? null);
        setWelcomeImageUrl(data.imageUrl ?? null);
        setWelcomeMessage(data.message ?? null);
        if (data.possibleQueries && data.possibleQueries.length > 0) {
          setPossibleQueries(data.possibleQueries);
        }
      });

      chatServiceRef.current.setServerUnavailableConfig(
        serverUnavailableMessage,
        serverUnavailableContactUrl,
        serverUnavailableContactLabel,
      );

      // Check for a saved conversation and connect to it
      const convId = chatServiceRef.current.getConversationId();
      if (convId) {
        setConversationId(convId);
        if (chatServiceRef.current.isConversationFinalized()) {
          setIsFinalized(true);
        } else {
          chatServiceRef.current.connectWebSocket();
          if (!useWs) {
            setConnectionState("connected");
          }
        }
      }
      // Pull initial static data
      if (chatServiceRef.current) {
        const queries = chatServiceRef.current.getPossibleQueries?.() || [];
        if (queries.length) setPossibleQueries(queries);
        const welcome = chatServiceRef.current.getWelcomeData?.();
        if (welcome) {
          setWelcomeTitle(welcome.title || null);
          setWelcomeImageUrl(welcome.imageUrl || null);
          setWelcomeMessage(welcome.message || null);
        }
        const thinking = chatServiceRef.current.getThinkingConfig?.();
        if (thinking) {
          setThinkingPhrases(thinking.phrases || []);
          setThinkingDelayMs(thinking.delayMs || 1000);
        }
        const meta = chatServiceRef.current.getChatInputMetadata?.();
        if (meta && typeof meta === "object" && Object.keys(meta).length > 0) {
          setChatInputMetadata(meta);
        }
        onConfigLoadedRef.current?.({ chatInputMetadata: meta ?? {} });
      }
    } else if (chatServiceRef.current) {
      // Just update metadata without re-initializing
      if (metadataChanged) {
        metadataRef.current = metadataString;
        chatServiceRef.current.setMetadata(metadata);
      }
    }

    // Always update handlers when callbacks change (without re-initializing)
    if (chatServiceRef.current) {
      chatServiceRef.current.setTakeoverHandler(() => {
        setIsTakenOver(true);
        setIsAgentTyping(false);
        if (onTakeoverRef.current) {
          onTakeoverRef.current();
        }
      });

      chatServiceRef.current.setFinalizedHandler(() => {
        setIsFinalized(true);
        setIsAgentTyping(false);
        if (onFinalizeRef.current) {
          onFinalizeRef.current();
        }
      });

      chatServiceRef.current.setServerUnavailableConfig(
        serverUnavailableMessage,
        serverUnavailableContactUrl,
        serverUnavailableContactLabel,
      );
    }

    // Cleanup only on unmount
    return () => {
      // Only cleanup on unmount, not on every dependency change
    };
  }, [
    baseUrl,
    apiKey,
    tenant,
    metadataString,
    language,
    useWs,
    usePoll,
    serverUnavailableMessage,
    serverUnavailableContactUrl,
    serverUnavailableContactLabel,
  ]);

  // Update language when it changes (without re-initializing the service)
  useEffect(() => {
    if (chatServiceRef.current) {
      chatServiceRef.current.setLanguage(language);
    }
  }, [language]);

  // Load messages for current pair when available
  useEffect(() => {
    const key = buildMessagesKey(apiKey, conversationId);
    if (!key) {
      setMessages([]);
      lastServerCreateTimeRef.current = 0;
      return;
    }
    try {
      const stored = localStorage.getItem(key);
      const parsed: ChatMessage[] = stored ? JSON.parse(stored) : [];
      setMessages(parsed);
      // Initialize last seen create_time from cached messages
      if (parsed.length) {
        const maxCreateTime = Math.max(
          ...parsed.map((m) => (m.create_time ? m.create_time : 0)),
        );
        lastServerCreateTimeRef.current = maxCreateTime;
      } else {
        lastServerCreateTimeRef.current = 0;
      }
    } catch (error) {
      setMessages([]);
      lastServerCreateTimeRef.current = 0;
    }
  }, [apiKey, conversationId, buildMessagesKey]);

  // Validate messages for takeover and finalized
  useEffect(() => {
    validateMessages(messages);
  }, [messages]);

  // Persist messages for current pair
  useEffect(() => {
    const key = buildMessagesKey(apiKey, conversationId);
    if (!key) return;
    try {
      localStorage.setItem(key, JSON.stringify(messages));
    } catch (error) {
      // ignore
    }
  }, [messages, apiKey, conversationId, buildMessagesKey]);

  // Heartbeat long polling when WebSocket is disabled and we have an in-progress conversation.
  // - Starts with a short interval
  // - Increases the interval over time (every successful poll)
  // - Retries up to 5 times on errors, then stops
  const HEARTBEAT_INITIAL_INTERVAL_MS = 2000;
  const HEARTBEAT_INTERVAL_STEP_MS = 5000;
  const HEARTBEAT_MAX_INTERVAL_MS = 30000;

  useEffect(() => {
    if (useWs || !conversationId || isFinalized) return;
    const svc = chatServiceRef.current;
    if (!svc) return;

    // Reset per-conversation flags so we only notify takeover/finalized once
    takeoverProcessedRef.current = false;
    finalizedProcessedRef.current = false;

    let cancelled = false;
    let timeoutId: number | null = null;

    const scheduleNext = (delayMs: number) => {
      if (cancelled) return;
      timeoutId = window.setTimeout(poll, delayMs);
    };

    const poll = async () => {
      if (cancelled) return;
      setIsPolling(true);
      try {
        const { status, pollMessages } = await svc.pollInProgressConversation();
        if (cancelled) return;

        // Reset failure counter on success
        heartbeatFailureCountRef.current = 0;

        // Only take messages newer than or equal to last seen create_time (seconds).
        // Use seconds consistently: poll messages are normalized to seconds in chatService.
        const lastServerCreateTime =
          Math.floor(Number(lastServerCreateTimeRef.current) || 0);

        const newMessagesRaw = (pollMessages || []).filter((m) => {
          const ct = Number((m as any).create_time);
          if (ct === 0 || !Number.isFinite(ct)) return false;
          return ct >= lastServerCreateTime;
        });

        if (newMessagesRaw.length > 0) {
          const speakerType = (speaker: string) => {
            if (speaker === "customer") return "customer";
            if (speaker === "agent") return "agent";
            return "special";
          };

          const text = (m: InProgressPollMessage) => {
            if (m.type === "takeover") return "Supervisor took over";
            if (m.type === "finalized") return "Conversation Finalized";
            return (m as any).text;
          };

          const newMessages: ChatMessage[] = newMessagesRaw.map((m) => ({
            message_id: (m as any).id,
            create_time: Number((m as any).create_time),
            start_time: Number((m as any).start_time ?? 0),
            end_time: Number((m as any).end_time ?? 0),
            speaker: speakerType((m as any).speaker),
            text: text(m),
            type: (m as any).type,
            feedback: (m as any).feedback,
          }));

          // Append only messages we don't already have (dedupe by message_id; same create_time can repeat every poll)
          if (newMessages.length > 0) {
            setMessages((prevMessages) => {
              const existingIds = new Set(
                prevMessages.map((m) => m.message_id).filter(Boolean),
              );
              const toAdd = newMessages.filter(
                (m) => m.message_id == null || !existingIds.has(m.message_id),
              );
              if (toAdd.length === 0) return prevMessages;
              const maxCreateTimeFromPoll = toAdd.reduce(
                (max, msg) =>
                  Number.isFinite(msg.create_time)
                    ? Math.max(max, msg.create_time)
                    : max,
                lastServerCreateTime,
              );
              lastServerCreateTimeRef.current = maxCreateTimeFromPoll;
              return [...prevMessages, ...toAdd];
            });
          }

          // Check new messages for takeover/finalize markers
          const hasTakeoverMessage = newMessages.some(
            (m) => m.type === "takeover",
          );
          const hasFinalizedMessage = newMessages.some(
            (m) => m.type === "finalized",
          );

          if ((status === "finalized" || hasFinalizedMessage) && !finalizedProcessedRef.current) {
            finalizedProcessedRef.current = true;
            setIsFinalized(true);
          } else if ((status === "takeover" || hasTakeoverMessage) && !takeoverProcessedRef.current) {
            takeoverProcessedRef.current = true;
            setIsTakenOver(true);
          }
        } else {
          // No new messages; still honor status if it indicates a terminal state (once per conversation)
          if (status === "finalized" && !finalizedProcessedRef.current) {
            finalizedProcessedRef.current = true;
            svc.notifyFinalizedFromPoll();
            setIsFinalized(true);
          } else if (status === "takeover" && !takeoverProcessedRef.current) {
            takeoverProcessedRef.current = true;
            svc.notifyTakeoverFromPoll();
            setIsTakenOver(true);
          }
        }

        if (status === "finalized") {
          // Mark finalized and let the effect cleanup prevent further scheduling
          setIsPolling(false);
          return;
        }

        // Increase polling interval over time on success
        const nextInterval = Math.min(
          (heartbeatIntervalRef.current || HEARTBEAT_INITIAL_INTERVAL_MS) +
            HEARTBEAT_INTERVAL_STEP_MS,
          HEARTBEAT_MAX_INTERVAL_MS,
        );
        heartbeatIntervalRef.current = nextInterval;
        setIsPolling(false);
        scheduleNext(nextInterval);
      } catch {
        if (cancelled) return;
        // Increment failure counter and stop after 5 consecutive failures
        heartbeatFailureCountRef.current += 1;
        if (heartbeatFailureCountRef.current >= 5) {
          setIsPolling(false);
          return;
        }
        const retryDelay =
          heartbeatIntervalRef.current || HEARTBEAT_INITIAL_INTERVAL_MS;
        scheduleNext(retryDelay);
      }
    };

    // Reset counters for this conversation and start immediately
    heartbeatFailureCountRef.current = 0;
    heartbeatIntervalRef.current = HEARTBEAT_INITIAL_INTERVAL_MS;

    if (usePoll && !useWs) {
      poll();
    }

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [useWs, conversationId, isFinalized, usePoll]);

  // Reset conversation
  const resetConversation = useCallback(
    async (reCaptchaToken?: string | undefined) => {
      if (!chatServiceRef.current) {
        return;
      }

      setConnectionState("connecting");
      setIsLoading(true);
      setMessages([]);
      setPossibleQueries([]);
      setWelcomeTitle(null);
      setWelcomeImageUrl(null);
      setWelcomeMessage(null);
      setThinkingPhrases([]);
      setThinkingDelayMs(1000);
      lastServerCreateTimeRef.current = 0;
      const key = buildMessagesKey(apiKey, conversationId);
      if (key) {
        localStorage.removeItem(key);
      }
      setIsFinalized(false);
      setIsTakenOver(false);
      setIsAgentTyping(false);

      try {
        // Reset the conversation in the chat service
        chatServiceRef.current.resetChatConversation();

        // Start a new conversation
        const convId =
          await chatServiceRef.current.startConversation(reCaptchaToken);
        setConversationId(convId);
        setConnectionState("connected");

        // Get possible queries from API response
        if (chatServiceRef.current.getPossibleQueries) {
          const queries = chatServiceRef.current.getPossibleQueries();
          if (queries && queries.length > 0) {
            setPossibleQueries(queries);
          }
        }
        // welcome and thinking data
        if (chatServiceRef.current.getWelcomeData) {
          const welcome = chatServiceRef.current.getWelcomeData();
          setWelcomeTitle(welcome.title || null);
          setWelcomeImageUrl(welcome.imageUrl || null);
          setWelcomeMessage(welcome.message || null);
        }
        if (chatServiceRef.current.getThinkingConfig) {
          const thinking = chatServiceRef.current.getThinkingConfig();
          setThinkingPhrases(thinking.phrases || []);
          setThinkingDelayMs(thinking.delayMs || 1000);
        }
        const meta = chatServiceRef.current.getChatInputMetadata?.();
        if (meta && typeof meta === "object" && Object.keys(meta).length > 0) {
          setChatInputMetadata(meta);
        }
        onConfigLoadedRef.current?.({
          chatInputMetadata:
            chatServiceRef.current.getChatInputMetadata?.() ?? {},
        });
      } catch (error) {
        setConnectionState("disconnected");
        setIsAgentTyping(false);
        if (onErrorRef.current && error instanceof Error) {
          onErrorRef.current(error);
        } else {
          // ignore
        }
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const uploadFile = useCallback(
    async (file: File): Promise<Attachment | null> => {
      const conversationId = chatServiceRef.current?.getConversationId();
      if (!conversationId) {
        return null;
      }

      try {
        const uploadResult = await chatServiceRef.current?.uploadFile(
          conversationId,
          file,
        );

        // construct the file url with the base url
        const file_url = new URL(uploadResult!.file_url!, baseUrl).href;

        const attachment: Attachment = {
          name: file.name,
          type: file.type,
          size: file.size,
          url: file_url,
          file_id: uploadResult?.file_id,
        };

        setPreloadedAttachments((prev) => [...prev, attachment]);
        return attachment;
      } catch (error: any) {
        if (isTokenExpiredError(error)) {
          resetToInitialState();
        }
        if (onErrorRef.current) {
          onErrorRef.current(error as Error);
        }
        return null;
      }
    },
    [
      apiKey,
      conversationId,
      buildMessagesKey,
      isTokenExpiredError,
      resetToInitialState,
    ],
  );

  // Send message
  const sendMessage = useCallback(
    async (
      text: string,
      files: File[] = [],
      extraMetadata?: Record<string, any>,
      reCaptchaToken?: string,
    ) => {
      if (!chatServiceRef.current) {
        throw new Error("Chat service not initialized");
      }

      try {
        setIsLoading(true);

        const newAttachments: Attachment[] = [];

        if (files.length > 0) {
          const uploadedFiles = files
            .map((f) =>
              preloadedAttachments.find(
                (pa) => pa.name === f.name && pa.size === f.size,
              ),
            )
            .filter(Boolean) as Attachment[];
          newAttachments.push(...uploadedFiles);
        }

        // Start typing immediately when user sends, unless conversation is taken over by a human
        if (!isTakenOver) {
          setIsAgentTyping(true);
        }

        await chatServiceRef.current.sendMessage(
          text,
          newAttachments,
          extraMetadata,
          reCaptchaToken,
        );

        setPreloadedAttachments([]);
      } catch (error: any) {
        setIsAgentTyping(false);
        if (isTokenExpiredError(error)) {
          resetToInitialState();
        } else if (isNetworkOrServerError(error)) {
          // Show custom server-unavailable message
          const now = Date.now() / 1000;
          const createTime =
            chatServiceRef.current?.getConversationCreateTime();
          const startTime = createTime != null ? now - createTime : 0;
          const endTime = startTime + 0.01;
          const specialMessage: ChatMessage = {
            create_time: now,
            start_time: startTime,
            end_time: endTime,
            speaker: "special",
            text:
              serverUnavailableMessage ?? DEFAULT_SERVER_UNAVAILABLE_MESSAGE,
            ...(serverUnavailableContactUrl && {
              linkUrl: serverUnavailableContactUrl,
              linkLabel:
                serverUnavailableContactLabel ??
                DEFAULT_SERVER_UNAVAILABLE_CONTACT_LABEL,
            }),
          };

          setMessages((prev) => [...prev, specialMessage]);
          // Don't call onError so the user only sees our custom message
        } else if (onErrorRef.current && error instanceof Error) {
          onErrorRef.current(error);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [
      preloadedAttachments,
      isTakenOver,
      isTokenExpiredError,
      resetToInitialState,
      serverUnavailableMessage,
      serverUnavailableContactUrl,
      serverUnavailableContactLabel,
    ],
  );

  const startConversation = useCallback(
    async (reCaptchaToken?: string | undefined) => {
      if (!chatServiceRef.current) {
        return;
      }
      try {
        setConnectionState("connecting");
        setIsLoading(true);

        // Reset state for new conversation
        setMessages([]);
        setPossibleQueries([]);
        const key = buildMessagesKey(apiKey, conversationId);
        if (key) {
          localStorage.removeItem(key);
        }
        setIsFinalized(false);
        setIsTakenOver(false);
        setIsAgentTyping(false);
        chatServiceRef.current.resetChatConversation();

        const convId =
          await chatServiceRef.current.startConversation(reCaptchaToken);
        setConversationId(convId);
        setConnectionState("connected");

        if (chatServiceRef.current.getPossibleQueries) {
          const queries = chatServiceRef.current.getPossibleQueries();
          if (queries && queries.length > 0) {
            setPossibleQueries(queries);
          }
        }
        if (chatServiceRef.current.getWelcomeData) {
          const welcome = chatServiceRef.current.getWelcomeData();
          setWelcomeTitle(welcome.title || null);
          setWelcomeImageUrl(welcome.imageUrl || null);
          setWelcomeMessage(welcome.message || null);
        }
        if (chatServiceRef.current.getThinkingConfig) {
          const thinking = chatServiceRef.current.getThinkingConfig();
          setThinkingPhrases(thinking.phrases || []);
          setThinkingDelayMs(thinking.delayMs || 1000);
        }
        const meta = chatServiceRef.current.getChatInputMetadata?.();
        if (meta && typeof meta === "object" && Object.keys(meta).length > 0) {
          setChatInputMetadata(meta);
        }
        onConfigLoadedRef.current?.({
          chatInputMetadata:
            chatServiceRef.current.getChatInputMetadata?.() ?? {},
        });
      } catch (error) {
        setConnectionState("disconnected");
        setIsAgentTyping(false);
        if (onErrorRef.current && error instanceof Error) {
          onErrorRef.current(error);
        } else {
          // ignore
        }
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  // Add feedback to an agent message
  const addFeedback = useCallback(
    async (
      messageId: string,
      value: "good" | "bad",
      feedbackMessage?: string,
    ) => {
      if (!chatServiceRef.current) {
        console.error("Cannot send feedback: ChatService not initialized");
        return;
      }
      if (!messageId) {
        console.error("Cannot send feedback: messageId is required");
        return;
      }

      try {
        await chatServiceRef.current.addFeedback(
          messageId,
          value,
          feedbackMessage,
        );

        const newFeedback: MessageFeedback = {
          feedback: value,
          feedback_message: feedbackMessage,
          feedback_timestamp: new Date().toISOString(),
        };

        setMessages((prev) =>
          prev.map((m) => {
            // Match by message_id or id field
            const msgId = m.message_id || (m as any).id;
            return msgId === messageId
              ? { ...m, feedback: [...(m.feedback || []), newFeedback] }
              : m;
          }),
        );
      } catch (error) {
        if (onErrorRef.current) {
          onErrorRef.current(error as Error);
        }
      }
    },
    [],
  );

  return {
    messages,
    isLoading,
    sendMessage,
    uploadFile,
    resetConversation,
    startConversation,
    connectionState,
    conversationId,
    possibleQueries,
    isTakenOver,
    isFinalized,
    isAgentTyping,
    addFeedback,
    welcomeTitle,
    welcomeImageUrl,
    welcomeMessage,
    thinkingPhrases,
    thinkingDelayMs,
    chatInputMetadata,
  };
};
