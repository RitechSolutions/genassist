import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatMessage } from "../types";

/**
 * "Read everything up to now" sentinel. The backend clamps last_read_sequence to
 * the conversation's true latest message, so the widget can report that the
 * visitor is caught up without knowing sequence numbers for WS-delivered messages
 * (which omit them). Postgres int4 max.
 */
const READ_ALL_SENTINEL = 2_147_483_647;

const EMIT_DEBOUNCE_MS = 350;

/** Stable identity for a message: server id when present, else its timestamp. */
export function messageIdentityKey(m: ChatMessage): string {
  return m.message_id || `t:${m.create_time}`;
}

/** Identity of the newest inbound (agent/supervisor) message, or null. */
function newestInboundKey(messages: ChatMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].speaker === "agent") return messageIdentityKey(messages[i]);
  }
  return null;
}

function indexOfKey(messages: ChatMessage[], key: string | null): number {
  if (!key) return -1;
  for (let i = 0; i < messages.length; i++) {
    if (messageIdentityKey(messages[i]) === key) return i;
  }
  return -1;
}

/** Count inbound messages strictly after `key` (all inbound when key is null/absent). */
export function countInboundAfter(messages: ChatMessage[], key: string | null): number {
  const idx = indexOfKey(messages, key);
  let count = 0;
  for (let i = idx + 1; i < messages.length; i++) {
    if (messages[i].speaker === "agent") count++;
  }
  return count;
}

/** Identity of the first inbound message strictly after `key`, or null. */
export function firstInboundKeyAfter(messages: ChatMessage[], key: string | null): string | null {
  const idx = indexOfKey(messages, key);
  for (let i = idx + 1; i < messages.length; i++) {
    if (messages[i].speaker === "agent") return messageIdentityKey(messages[i]);
  }
  return null;
}

export interface UseReadReporterOptions {
  /** Master switch (the `readReceipts` prop). */
  enabled: boolean;
  /** Whether the chat surface is open/mounted (e.g. a floating panel that's been
   *  opened). Gates emission and re-attaches the observer once the bottom sentinel
   *  mounts. */
  active: boolean;
  messages: ChatMessage[];
  conversationId: string | null;
  isFinalized: boolean;
  markRead: (lastReadSequence: number) => void;
  /** localStorage key for the persisted local "seen" marker, or null to skip. */
  persistKey: string | null;
}

export interface ReadTracking {
  /** Inbound messages the visitor hasn't seen yet (drives the launcher badge). */
  unreadCount: number;
  /** Identity of the message to render the "New messages" divider before, or null
   *  (no divider). */
  dividerBeforeKey: string | null;
  /** Callback ref to attach to the sentinel at the bottom of the thread. Using a
   *  callback ref (not a ref object) means the visibility observer attaches exactly
   *  when the sentinel mounts — robust to panels that mount a render *after* they
   *  open (e.g. the floating widget), where an effect keyed on "open" would miss it. */
  registerBottom: (el: HTMLElement | null) => void;
}

/**
 * Two jobs, both keyed off "is the visitor actively viewing the newest message":
 *  1. Reports the visitor's read state upstream (so a supervisor's console shows
 *     when their reply was read) — a debounced, once-per-new-message mark-read.
 *  2. Tracks the visitor's own local unread state — an unread count for the
 *     launcher badge and an anchor for the "New messages" divider (snapshotted
 *     when the visitor (re)engages, so it marks where they left off and survives
 *     the reading session).
 */
export function useReadReporter({
  enabled,
  active,
  messages,
  conversationId,
  isFinalized,
  markRead,
  persistKey,
}: UseReadReporterOptions): ReadTracking {
  const [atBottom, setAtBottom] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const [focused, setFocused] = useState<boolean>(() => {
    if (typeof document === "undefined") return true;
    const visible = document.visibilityState === "visible";
    const hasFocus = typeof document.hasFocus === "function" ? document.hasFocus() : true;
    return visible && hasFocus;
  });
  // Newest inbound message the visitor has seen (drives the unread count).
  const [seenKey, setSeenKey] = useState<string | null>(null);
  // Frozen snapshot of the seen marker at engage-time (drives the divider).
  const [dividerKey, setDividerKey] = useState<string | null>(null);

  const seenKeyRef = useRef<string | null>(null);
  seenKeyRef.current = seenKey;
  const lastEmittedKeyRef = useRef<string | null>(null);
  const prevEngagedRef = useRef(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const newestInbound = useMemo(() => newestInboundKey(messages), [messages]);

  // Load the persisted seen marker when the conversation changes; reset the divider.
  useEffect(() => {
    lastEmittedKeyRef.current = null;
    prevEngagedRef.current = false;
    setDividerKey(null);
    if (!persistKey) {
      setSeenKey(null);
      return;
    }
    try {
      setSeenKey(localStorage.getItem(persistKey) || null);
    } catch {
      setSeenKey(null);
    }
  }, [persistKey]);

  // Persist the seen marker.
  useEffect(() => {
    if (!persistKey || !seenKey) return;
    try {
      localStorage.setItem(persistKey, seenKey);
    } catch {
      // ignore
    }
  }, [persistKey, seenKey]);

  // Track window focus + tab visibility.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const update = () => {
      const visible = document.visibilityState === "visible";
      const hasFocus = typeof document.hasFocus === "function" ? document.hasFocus() : true;
      setFocused(visible && hasFocus);
    };
    update();
    window.addEventListener("focus", update);
    window.addEventListener("blur", update);
    document.addEventListener("visibilitychange", update);
    return () => {
      window.removeEventListener("focus", update);
      window.removeEventListener("blur", update);
      document.removeEventListener("visibilitychange", update);
    };
  }, []);

  // Attach a visibility observer to the bottom sentinel the instant it mounts, and
  // tear it down when it unmounts (e.g. a floating panel closing). Driven by the DOM
  // node itself rather than an "is open" flag, so it can't miss a late-mounting panel.
  const registerBottom = useCallback((el: HTMLElement | null) => {
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    if (!el) {
      setAtBottom(false);
      return;
    }
    if (typeof IntersectionObserver === "undefined") {
      setAtBottom(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) setAtBottom(entry.isIntersecting);
      },
      { threshold: 0.1 }
    );
    observer.observe(el);
    observerRef.current = observer;
  }, []);

  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
    };
  }, []);

  const engaged = enabled && active && focused && !!conversationId && !isFinalized;
  const viewingBottom = engaged && atBottom;

  // Snapshot the divider position when the visitor (re)engages, so the "New
  // messages" line marks where they left off and persists through the session.
  useEffect(() => {
    const wasEngaged = prevEngagedRef.current;
    prevEngagedRef.current = engaged;
    if (engaged && !wasEngaged) {
      setDividerKey(seenKeyRef.current);
    }
  }, [engaged]);

  // While the newest message is on screen: advance the seen marker (clears unread)
  // and report read upstream (debounced, once per new inbound message).
  useEffect(() => {
    if (!viewingBottom || !newestInbound) return;
    if (newestInbound !== seenKeyRef.current) {
      setSeenKey(newestInbound);
    }
    if (newestInbound !== lastEmittedKeyRef.current) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      const keyAtSchedule = newestInbound;
      debounceRef.current = setTimeout(() => {
        debounceRef.current = null;
        lastEmittedKeyRef.current = keyAtSchedule;
        markRead(READ_ALL_SENTINEL);
      }, EMIT_DEBOUNCE_MS);
    }
  }, [viewingBottom, newestInbound, markRead]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const unreadCount = useMemo(
    () => (enabled ? countInboundAfter(messages, seenKey) : 0),
    [enabled, messages, seenKey]
  );

  // Only show the divider when there is a real prior-seen boundary (dividerKey set);
  // on a brand-new conversation there is nothing "old" to separate from.
  const dividerBeforeKey = useMemo(
    () => (enabled && dividerKey !== null ? firstInboundKeyAfter(messages, dividerKey) : null),
    [enabled, messages, dividerKey]
  );

  return { unreadCount, dividerBeforeKey, registerBottom };
}
