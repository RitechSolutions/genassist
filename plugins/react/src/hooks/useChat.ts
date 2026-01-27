import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { ChatService } from '../services/chatService';
import { ChatMessage, Attachment, MessageFeedback } from '../types';

export interface UseChatProps {
  baseUrl: string;
  apiKey: string;
  tenant?: string | undefined;
  metadata?: Record<string, any>;
  language?: string;
  onError?: (error: Error) => void;
  onTakeover?: () => void;
  onFinalize?: () => void;
}

export const useChat = ({ baseUrl, apiKey, tenant, metadata, language, onError, onTakeover, onFinalize }: UseChatProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [preloadedAttachments, setPreloadedAttachments] = useState<Attachment[]>([]);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const [isAgentTyping, setIsAgentTyping] = useState<boolean>(false);
  const chatServiceRef = useRef<ChatService | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [possibleQueries, setPossibleQueries] = useState<string[]>([]);
  const [welcomeTitle, setWelcomeTitle] = useState<string | null>(null);
  const [welcomeImageUrl, setWelcomeImageUrl] = useState<string | null>(null);
  const [welcomeMessage, setWelcomeMessage] = useState<string | null>(null);
  const [thinkingPhrases, setThinkingPhrases] = useState<string[]>([]);
  const [thinkingDelayMs, setThinkingDelayMs] = useState<number>(1000);
  const [isTakenOver, setIsTakenOver] = useState<boolean>(false);
  const [isFinalized, setIsFinalized] = useState<boolean>(false);

  // Scoped messages key for apiKey, conversatioId
  const buildMessagesKey = useCallback((apiKeyVal: string, convId: string | null) => {
    if (!convId) return null;
    return `genassist_conversation_messages:${apiKeyVal}:${convId}`;
  }, []);

  // Deep compare metadata to prevent unnecessary re-initializations
  // Only re-initialize if metadata actually changes (by value, not reference)
  const metadataString = useMemo(() => JSON.stringify(metadata || {}), [metadata]);
  const metadataRef = useRef<string>(metadataString);
  const prevBaseUrlRef = useRef<string>(baseUrl);
  const prevApiKeyRef = useRef<string>(apiKey);
  const prevTenantRef = useRef<string | undefined>(tenant);

  // Store callbacks in refs so they don't trigger re-initialization
  const onErrorRef = useRef(onError);
  const onTakeoverRef = useRef(onTakeover);
  const onFinalizeRef = useRef(onFinalize);

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

  // Initialize chat service - only when baseUrl, apiKey, tenant, or metadata actually change
  useEffect(() => {
    const metadataChanged = metadataRef.current !== metadataString;
    const baseUrlChanged = prevBaseUrlRef.current !== baseUrl;
    const apiKeyChanged = prevApiKeyRef.current !== apiKey;
    const tenantChanged = prevTenantRef.current !== tenant;
    
    // Only re-initialize for connection-related changes, NOT for metadata changes
    const needsReinit = !chatServiceRef.current || baseUrlChanged || apiKeyChanged || tenantChanged;

    if (needsReinit) {
      // Update refs
      if (baseUrlChanged) prevBaseUrlRef.current = baseUrl;
      if (apiKeyChanged) prevApiKeyRef.current = apiKey;
      if (tenantChanged) prevTenantRef.current = tenant;
      if (metadataChanged) metadataRef.current = metadataString;

      // Clean up existing service if it exists
      if (chatServiceRef.current) {
        chatServiceRef.current.disconnect();
        chatServiceRef.current.setWelcomeDataHandler(null);
      }
      
      chatServiceRef.current = new ChatService(baseUrl, apiKey, metadata, tenant, language);
      
      // Set up handlers
      chatServiceRef.current.setMessageHandler((message: ChatMessage) => {
        const normalizedMessage: ChatMessage = {
          ...message,
          create_time: (!message.create_time || isNaN(message.create_time))
            ? Math.floor(Date.now() / 1000)
            : message.create_time,
        };

        setMessages(prevMessages => [...prevMessages, normalizedMessage]);
        // Stop typing animation when agent or system message arrives
        if (normalizedMessage.speaker === 'agent' || normalizedMessage.speaker === 'special') {
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
        if (state !== 'connected') {
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

      // Check for a saved conversation and connect to it
      const convId = chatServiceRef.current.getConversationId();
      if (convId) {
        setConversationId(convId);
        if (chatServiceRef.current.isConversationFinalized()) {
          setIsFinalized(true);
        } else {
          chatServiceRef.current.connectWebSocket();
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
    }

    // Cleanup only on unmount
    return () => {
      // Only cleanup on unmount, not on every dependency change
    };
  }, [baseUrl, apiKey, tenant, metadataString, language]);

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
      return;
    }
    try {
      const stored = localStorage.getItem(key);
      setMessages(stored ? JSON.parse(stored) : []);
    } catch (error) {
      setMessages([]);
    }
  }, [apiKey, conversationId, buildMessagesKey]);

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

  // Reset conversation
  const resetConversation = useCallback(async (reCaptchaToken: string | undefined) => {
    if (!chatServiceRef.current) {
      return;
    }
    
    setConnectionState('connecting');
    setIsLoading(true);
    setMessages([]);
    setPossibleQueries([]);
    setWelcomeTitle(null);
    setWelcomeImageUrl(null);
    setWelcomeMessage(null);
    setThinkingPhrases([]);
    setThinkingDelayMs(1000);
    const key = buildMessagesKey(apiKey, conversationId);
    if (key) {
      localStorage.removeItem(key);
    }
    setIsFinalized(false);
    setIsTakenOver(false);
    setIsAgentTyping(false);
    
    try {
      // Reset the conversation in the chat service
      chatServiceRef.current.resetConversation();
      
      // Start a new conversation
      const convId = await chatServiceRef.current.startConversation(reCaptchaToken);
      setConversationId(convId);
      setConnectionState('connected');

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
    } catch (error) {
      setConnectionState('disconnected');
      setIsAgentTyping(false);
      if (onErrorRef.current && error instanceof Error) {
        onErrorRef.current(error);
      } else {
        // ignore
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const uploadFile = useCallback(async (file: File): Promise<Attachment | null> => {
    if (!chatServiceRef.current || !chatServiceRef.current.getConversationId()) {
      return null;
    }

    try {
      const { fileUrl } = await chatServiceRef.current.uploadFile(
        chatServiceRef.current.getConversationId() as string,
        file
      );
      
      const attachment: Attachment = {
        name: file.name,
        type: file.type,
        size: file.size,
        url: fileUrl,
      };

      setPreloadedAttachments(prev => [...prev, attachment]);
      return attachment;
    } catch (error) {
      if (onErrorRef.current) {
        onErrorRef.current(error as Error);
      }
      return null;
    }
  }, []);

  // Send message
  const sendMessage = useCallback(async (text: string, files: File[] = [], extraMetadata?: Record<string, any>, reCaptchaToken?: string) => {
    if (!chatServiceRef.current) {
      throw new Error('Chat service not initialized');
    }

    try {
      setIsLoading(true);

      const newAttachments: Attachment[] = [];
      
      if (files.length > 0) {
        const uploadedFiles = files.map(f => preloadedAttachments.find(pa => pa.name === f.name && pa.size === f.size)).filter(Boolean) as Attachment[];
        newAttachments.push(...uploadedFiles);
      }

      // Start typing immediately when user sends, unless conversation is taken over by a human
      if (!isTakenOver) {
        setIsAgentTyping(true);
      }
      await chatServiceRef.current.sendMessage(text, newAttachments, extraMetadata, reCaptchaToken);

      setPreloadedAttachments([]);

    } catch (error) {
      setIsAgentTyping(false);
      if (onErrorRef.current && error instanceof Error) {
        onErrorRef.current(error);
      } else {
        // ignore
      }
    } finally {
      setIsLoading(false);
    }
  }, [preloadedAttachments, isTakenOver]);

  const startConversation = useCallback(async (reCaptchaToken: string | undefined) => {
    if (!chatServiceRef.current) {
      return;
    }
    try {
      setConnectionState('connecting');
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
      chatServiceRef.current.resetConversation();

      const convId = await chatServiceRef.current.startConversation(reCaptchaToken);
      setConversationId(convId);
      setConnectionState('connected');

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
    } catch (error) {
      setConnectionState('disconnected');
      setIsAgentTyping(false);
      if (onErrorRef.current && error instanceof Error) {
        onErrorRef.current(error);
      } else {
        // ignore
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Add feedback to an agent message
  const addFeedback = useCallback(
    async (messageId: string, value: 'good' | 'bad', feedbackMessage?: string) => {
      if (!chatServiceRef.current) {
        console.error('Cannot send feedback: ChatService not initialized');
        return;
      }
      if (!messageId) {
        console.error('Cannot send feedback: messageId is required');
        return;
      }
      
      try {
        await chatServiceRef.current.addFeedback(messageId, value, feedbackMessage);

        const newFeedback: MessageFeedback = {
          feedback: value,
          feedback_message: feedbackMessage,
          feedback_timestamp: new Date().toISOString(),
        };

        setMessages(prev =>
          prev.map(m => {
            // Match by message_id or id field
            const msgId = m.message_id || (m as any).id;
            return msgId === messageId
              ? { ...m, feedback: [...(m.feedback || []), newFeedback] }
              : m;
          })
        );
      } catch (error) {
        if (onErrorRef.current) {
          onErrorRef.current(error as Error);
        }
      }
    },
    []
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
  };
};
