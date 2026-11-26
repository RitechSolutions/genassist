import { useRef, useLayoutEffect, useEffect, useState, useCallback } from 'react';
import { ChatMessage } from '../types';
import { isLauncherMode } from '../utils/chatMode';

const PIN_PEEK = 24;

export const LATEST_QUESTION_ATTR = 'data-ga-latest-question';

/** Scroll offset that pins the visitor's question near the top, or its bottom at mid-screen when it is tall.
 *  `peek` is the gap kept above the question (more when a header floats over the list). */
export function pinTop(questionTop: number, questionBottom: number, viewportHeight: number, peek: number = PIN_PEEK): number {
  return Math.max(0, questionTop - peek, questionBottom - viewportHeight / 2);
}

/** Gap above a pinned question: the container's CSS scroll-padding-top when it sets one
 *  (a header overlaying the list), otherwise PIN_PEEK. */
export function pinPeek(container: HTMLElement): number {
  if (typeof window === 'undefined' || !window.getComputedStyle) return PIN_PEEK;
  const padding = parseFloat(window.getComputedStyle(container).scrollPaddingTop);
  return Number.isFinite(padding) && padding > PIN_PEEK ? padding : PIN_PEEK;
}

/**
 * The pin offset the spacer makes room for. While a reply is awaited it is the full pin, so
 * the question can be scrolled up to it; once the reply is in, it is capped at where the
 * reader actually is, so the spacer only holds the current view and never leaves empty
 * room to scroll into below a short conversation.
 */
export function heldTop(pin: number, scrollTop: number, awaitingReply: boolean): number {
  return awaitingReply ? pin : Math.min(pin, Math.max(0, scrollTop));
}

export function spacerHeight(top: number, viewportHeight: number, contentHeight: number): number {
  return Math.max(0, top + viewportHeight - contentHeight);
}

export function isAtBottom({ scrollHeight, scrollTop, clientHeight }: Pick<HTMLElement, 'scrollHeight' | 'scrollTop' | 'clientHeight'>): boolean {
  return scrollHeight - scrollTop - clientHeight <= 100;
}

/** Identity of a visitor's message, stable when the server later adds its id. */
export function questionKey(question: ChatMessage | undefined): string | null {
  return question ? question.client_id ?? question.message_id ?? String(question.create_time) : null;
}

interface UseScrollManagementOptions {
  messages: ChatMessage[];
  latestQuestion: ChatMessage | undefined;
  isAgentTyping: boolean;
  conversationId: string | null | undefined;
  isFloatingOpen: boolean;
  mode: string;
}

export function useScrollManagement({
  messages,
  latestQuestion,
  isAgentTyping,
  conversationId,
  isFloatingOpen,
  mode,
}: UseScrollManagementOptions) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const hasAnchoredHistory = useRef(false);
  const isUserAtBottomRef = useRef(true);
  const prevIsFloatingOpenRef = useRef(isFloatingOpen);
  const spacerRef = useRef<HTMLDivElement>(null);
  const lastQuestionKeyRef = useRef<string | null>(null);
  const holdingRef = useRef(false);
  const awaitingReplyRef = useRef(false);
  // Reactive flag driving the "jump to latest" affordance — true when the conversation
  // is scrollable and the user has scrolled up far enough from the newest message.
  const [showScrollButton, setShowScrollButton] = useState(false);

  const updateScrollButton = useCallback(() => {
    const el = chatContainerRef.current;
    if (!el) {
      setShowScrollButton(false);
      return;
    }
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const isScrollable = el.scrollHeight - el.clientHeight > 40;
    setShowScrollButton(isScrollable && distanceFromBottom > 140);
  }, []);

  // Public jump-to-latest used by the scroll button. Forces a scroll regardless of the
  // "is the user at the bottom" gate and immediately hides the affordance.
  const scrollToLatest = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const container = chatContainerRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior });
    isUserAtBottomRef.current = true;
    setShowScrollButton(false);
  }, []);

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

  const fitSpacer =(): number | null => {
    const container = chatContainerRef.current;
    const spacer = spacerRef.current;
    if (!container || !spacer) return null;
    const question = holdingRef.current ? container.querySelector<HTMLElement>(`[${LATEST_QUESTION_ATTR}]`) : null;
    if (!question) {
      spacer.style.height = '0px';
      return null;
    }
    const offset = container.scrollTop - container.getBoundingClientRect().top;
    const rect = question.getBoundingClientRect();
    const pin = pinTop(rect.top + offset, rect.bottom + offset, container.clientHeight, pinPeek(container));
    const top = heldTop(pin, container.scrollTop, awaitingReplyRef.current);
    spacer.style.height = `${spacerHeight(top, container.clientHeight, container.scrollHeight - spacer.offsetHeight)}px`;
    return top;
  };

  useLayoutEffect(() => {
    const key = questionKey(latestQuestion);
    const isNewQuestion = key !== null && key !== lastQuestionKeyRef.current;
    lastQuestionKeyRef.current = key;
    if (!messages.length) return;
    if (!hasAnchoredHistory.current) {
      anchorHistory();
      return;
    }
    if (isNewQuestion) {
      holdingRef.current = true;
      // Size the spacer for the full pin: the reply is now awaited.
      awaitingReplyRef.current = true;
      const top = fitSpacer();
      awaitingReplyRef.current = top !== null;
      if (top !== null) chatContainerRef.current?.scrollTo({ top, behavior: 'smooth' });
      return;
    }
    if (awaitingReplyRef.current) {
      const speaker = messages[messages.length - 1].speaker;
      if (speaker !== 'agent' && speaker !== 'special') return;
      awaitingReplyRef.current = false;
      // A reply growing under a still reader fires no scroll event, so the flag can be stale.
      if (chatContainerRef.current) isUserAtBottomRef.current = isAtBottom(chatContainerRef.current);
      return;
    }
    scrollToBottom('smooth', false);
  }, [messages]);

  useLayoutEffect(() => {
    fitSpacer();
    updateScrollButton();
  });

  useLayoutEffect(() => {
    if (isAgentTyping && !awaitingReplyRef.current) scrollToBottom('auto', true);
  }, [isAgentTyping]);

  useEffect(() => {
    hasAnchoredHistory.current = false;
    holdingRef.current = false;
    awaitingReplyRef.current = false;
  }, [conversationId]);

  useEffect(() => {
    if ((isLauncherMode(mode) || mode === 'fullscreen' || mode === 'inputbar') && isFloatingOpen && !prevIsFloatingOpenRef.current && messages.length > 0) {
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

    let lastHeight = el.clientHeight;
    const resizeObserver = new ResizeObserver(() => {
      // The list got shorter (the on-screen keyboard opened, the composer grew): keep its
      // bottom where it was, so the newest messages stay in view rather than the oldest.
      const shrunkBy = lastHeight - el.clientHeight;
      lastHeight = el.clientHeight;
      if (shrunkBy > 0) el.scrollTop = shrunkBy + el.scrollTop;
      fitSpacer();
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

    const handleScroll = () => {
      isUserAtBottomRef.current = isAtBottom(container);
    };
    container.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => {
      container.removeEventListener('scroll', handleScroll);
    };
  }, []);

  // Scroll-button tracking. Kept separate from the isUserAtBottom listener above so it can
  // (re)attach when the container mounts — the floating/input-bar panels only render their
  // scroll container once opened, so depending on isFloatingOpen re-runs this on open.
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) {
      setShowScrollButton(false);
      return;
    }
    updateScrollButton();
    container.addEventListener('scroll', updateScrollButton, { passive: true });
    return () => {
      container.removeEventListener('scroll', updateScrollButton);
    };
  }, [isFloatingOpen, messages.length, isAgentTyping, updateScrollButton]);

  return {
    messagesEndRef,
    chatContainerRef,
    spacerRef,
    showScrollButton,
    scrollToLatest,
  };
}
