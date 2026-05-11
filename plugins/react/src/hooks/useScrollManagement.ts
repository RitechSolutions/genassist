import { useRef, useLayoutEffect, useEffect } from 'react';
import { ChatMessage } from '../types';

interface UseScrollManagementOptions {
  messages: ChatMessage[];
  isAgentTyping: boolean;
  currentThinkingPartIndex: number;
  currentThinkingPartsLength: number;
  conversationId: string | null | undefined;
  isFloatingOpen: boolean;
  mode: string;
}

export function useScrollManagement({
  messages,
  isAgentTyping,
  currentThinkingPartIndex,
  currentThinkingPartsLength,
  conversationId,
  isFloatingOpen,
  mode,
}: UseScrollManagementOptions) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const hasAnchoredHistory = useRef(false);
  const isUserAtBottomRef = useRef(true);
  const prevIsFloatingOpenRef = useRef(isFloatingOpen);

  const anchorHistory = () => {
    const el = chatContainerRef.current;
    if (!el || !messages.length || hasAnchoredHistory.current) return;
    if (el.clientHeight === 0) return;
    el.scrollTop = el.scrollHeight;
    hasAnchoredHistory.current = true;
    isUserAtBottomRef.current = true;
  };

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth', force: boolean = false) => {
    const container = chatContainerRef.current;
    const el = messagesEndRef.current;
    if (!container || !el) return;

    if (!force && !isUserAtBottomRef.current) {
      return;
    }

    const doScroll = () => {
      container.scrollTo({ top: container.scrollHeight, behavior });
      isUserAtBottomRef.current = true;
    };
    if (behavior === 'auto') {
      doScroll();
    } else {
      requestAnimationFrame(doScroll);
    }
  };

  useLayoutEffect(() => {
    if (!messages.length) return;
    if (hasAnchoredHistory.current) {
      scrollToBottom('smooth', false);
    } else {
      anchorHistory();
    }
  }, [messages]);

  useLayoutEffect(() => {
    if (!isAgentTyping) return;
    scrollToBottom('auto', true);
  }, [isAgentTyping, currentThinkingPartIndex, currentThinkingPartsLength]);

  useEffect(() => {
    hasAnchoredHistory.current = false;
  }, [conversationId]);

  useEffect(() => {
    if ((mode === 'floating' || mode === 'fullscreen') && isFloatingOpen && !prevIsFloatingOpenRef.current && messages.length > 0) {
      hasAnchoredHistory.current = false;
      isUserAtBottomRef.current = true;

      const scrollWhenVisible = () => {
        const container = chatContainerRef.current;
        if (!container) {
          requestAnimationFrame(scrollWhenVisible);
          return;
        }

        if (container.clientHeight === 0) {
          requestAnimationFrame(scrollWhenVisible);
          return;
        }

        container.scrollTop = container.scrollHeight;
        hasAnchoredHistory.current = true;
        isUserAtBottomRef.current = true;
      };

      requestAnimationFrame(() => {
        requestAnimationFrame(scrollWhenVisible);
      });
    }
    prevIsFloatingOpenRef.current = isFloatingOpen;
  }, [isFloatingOpen, mode]);

  useEffect(() => {
    if (!messages.length) return;
    const el = chatContainerRef.current;
    if (!el) return;

    const resizeObserver = new ResizeObserver(() => {
      if (isUserAtBottomRef.current) {
        anchorHistory();
      }
    });
    resizeObserver.observe(el);

    anchorHistory();

    return () => {
      resizeObserver.disconnect();
    };
  }, [messages]);

  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;

    const isAtBottom = (threshold: number = 100): boolean => {
      if (!container) return true;
      const { scrollTop, scrollHeight, clientHeight } = container;
      return scrollHeight - scrollTop - clientHeight <= threshold;
    };
    const handleScroll = () => {
      isUserAtBottomRef.current = isAtBottom();
    };
    container.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => {
      container.removeEventListener('scroll', handleScroll);
    };
  }, []);

  return {
    messagesEndRef,
    chatContainerRef,
  };
}
