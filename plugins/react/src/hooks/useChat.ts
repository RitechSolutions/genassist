import { useState, useEffect, useCallback, useRef } from 'react';
import { ChatService } from '../services/chatService';
import { ChatMessage } from '../types';

export interface UseChatProps {
  baseUrl: string;
  apiKey: string;
  onError?: (error: Error) => void;
  onTakeover?: () => void;
}

export const useChat = ({ baseUrl, apiKey, onError, onTakeover }: UseChatProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const chatServiceRef = useRef<ChatService | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [possibleQueries, setPossibleQueries] = useState<string[]>([]);
  const [isTakenOver, setIsTakenOver] = useState<boolean>(false);

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

    // Initialize conversation (using existing one or starting new)
    const initChat = async () => {
      try {
        setConnectionState('connecting');
        setIsLoading(true);
        
        if (chatServiceRef.current) {
          const convId = await chatServiceRef.current.initializeConversation();
          setConversationId(convId);
          setConnectionState('connected');

          // Get possible queries from API response
          if (chatServiceRef.current.getPossibleQueries) {
            const queries = chatServiceRef.current.getPossibleQueries();
            if (queries && queries.length > 0) {
              setPossibleQueries(queries);
            }
          }
        }
      } catch (error) {
        setConnectionState('disconnected');
        if (onError && error instanceof Error) {
          onError(error);
        } else {
          console.error('Failed to initialize conversation:', error);
        }
      } finally {
        setIsLoading(false);
      }
    };

    initChat();

    // Cleanup
    return () => {
      if (chatServiceRef.current) {
        chatServiceRef.current.disconnect();
      }
    };
  }, [baseUrl, apiKey, onError, onTakeover]);

  // Reset conversation
  const resetConversation = useCallback(async () => {
    if (!chatServiceRef.current) {
      return;
    }
    
    setConnectionState('connecting');
    setIsLoading(true);
    setMessages([]);
    setPossibleQueries([]);
    
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

    const now = Date.now();
    const userMessage: ChatMessage = {
      create_time: now,
      start_time: now / 1000,
      end_time: now / 1000 + 0.01,
      speaker: 'customer',
      text
    };

    // Optimistically add user message to UI
    // setMessages(prevMessages => [...prevMessages, userMessage]);
    
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

  return {
    messages,
    isLoading,
    sendMessage,
    resetConversation,
    connectionState,
    conversationId,
    possibleQueries,
    isTakenOver
  };
}; 