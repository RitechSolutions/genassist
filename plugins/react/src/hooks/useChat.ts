import { useState, useEffect, useCallback, useRef } from 'react';
import { ChatService } from '../services/chatService';
import { ChatMessage } from '../types';

export interface UseChatProps {
  baseUrl: string;
  apiKey: string;
  onError?: (error: Error) => void;
  onTakeover?: () => void;
  onFinalize?: () => void;
}

export const useChat = ({ baseUrl, apiKey, onError, onTakeover, onFinalize }: UseChatProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const storedMessages = localStorage.getItem('chatMessages');
      return storedMessages ? JSON.parse(storedMessages) : [];
    } catch (error) {
      console.error('Error loading messages from localStorage:', error);
      return [];
    }
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const chatServiceRef = useRef<ChatService | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [possibleQueries, setPossibleQueries] = useState<string[]>([]);
  const [isTakenOver, setIsTakenOver] = useState<boolean>(false);
  const [isFinalized, setIsFinalized] = useState<boolean>(false);

  // Initialize chat service
  useEffect(() => {
    chatServiceRef.current = new ChatService(baseUrl, apiKey);
    
    chatServiceRef.current.setMessageHandler((message: ChatMessage) => {
      setMessages(prevMessages => [...prevMessages, message]);
    });

    chatServiceRef.current.setTakeoverHandler(() => {
      setIsTakenOver(true);
      if (onTakeover) {
        onTakeover();
      }
    });

    chatServiceRef.current.setFinalizedHandler(() => {
      setIsFinalized(true);
      if (onFinalize) {
        onFinalize();
      }
    });

    chatServiceRef.current.setConnectionStateHandler(setConnectionState);

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

    // Cleanup
    return () => {
      if (chatServiceRef.current) {
        chatServiceRef.current.disconnect();
      }
    };
  }, [baseUrl, apiKey, onError, onTakeover, onFinalize]);

  useEffect(() => {
    try {
      localStorage.setItem('chatMessages', JSON.stringify(messages));
    } catch (error) {
      console.error('Error saving messages to localStorage:', error);
    }
  }, [messages]);

  // Reset conversation
  const resetConversation = useCallback(async () => {
    if (!chatServiceRef.current) {
      return;
    }
    
    setConnectionState('connecting');
    setIsLoading(true);
    setMessages([]);
    setPossibleQueries([]);
    localStorage.removeItem('chatMessages');
    setIsFinalized(false);
    
    try {
      // Reset the conversation in the chat service
      chatServiceRef.current.resetConversation();
      
      // Start a new conversation
      const convId = await chatServiceRef.current.startConversation();
      setConversationId(convId);
      setConnectionState('connected');

      // Get possible queries from API response
      if (chatServiceRef.current.getPossibleQueries) {
        const queries = chatServiceRef.current.getPossibleQueries();
        if (queries && queries.length > 0) {
          setPossibleQueries(queries);
        }
      }
    } catch (error) {
      setConnectionState('disconnected');
      if (onError && error instanceof Error) {
        onError(error);
      } else {
        console.error('Failed to reset conversation:', error);
      }
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  // Send message
  const sendMessage = useCallback(async (text: string) => {
    if (!chatServiceRef.current) {
      throw new Error('Chat service not initialized');
    }

    try {
      setIsLoading(true);
      await chatServiceRef.current.sendMessage(text);
    } catch (error) {
      if (onError && error instanceof Error) {
        onError(error);
      } else {
        console.error('Failed to send message:', error);
      }
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  const startConversation = useCallback(async () => {
    if (!chatServiceRef.current) {
      return;
    }
    try {
      setConnectionState('connecting');
      setIsLoading(true);
      
      // Reset state for new conversation
      setMessages([]);
      setPossibleQueries([]);
      localStorage.removeItem('chatMessages');
      setIsFinalized(false);
      chatServiceRef.current.resetConversation();

      const convId = await chatServiceRef.current.startConversation();
      setConversationId(convId);
      setConnectionState('connected');

      if (chatServiceRef.current.getPossibleQueries) {
        const queries = chatServiceRef.current.getPossibleQueries();
        if (queries && queries.length > 0) {
          setPossibleQueries(queries);
        }
      }
    } catch (error) {
      setConnectionState('disconnected');
      if (onError && error instanceof Error) {
        onError(error);
      } else {
        console.error('Failed to start conversation:', error);
      }
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  return {
    messages,
    isLoading,
    sendMessage,
    resetConversation,
    startConversation,
    connectionState,
    conversationId,
    possibleQueries,
    isTakenOver,
    isFinalized
  };
}; 