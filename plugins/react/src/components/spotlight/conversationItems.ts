import type { ChatMessage } from '../../types';
import { messageIdentityKey } from '../../hooks/useReadReporter';

/** A completed or in-progress live-voice exchange (mirrors GenAgentChat's LiveTurn). */
export interface LiveTurnLike {
  user: string;
  agent: string;
  createTime: number;
}

interface ItemBase {
  /** Stable React key: survives the optimistic → server-confirmed swap of a message. */
  key: string;
  /** Epoch seconds to show as a centred time separator above this item, if any. */
  timeSeparator?: number;
  /** Render the "New message" marker above this item (read receipts). */
  showNewDivider: boolean;
}

export interface WelcomeItem extends ItemBase {
  kind: 'welcome';
  title: string;
  content: string;
  imageUrl?: string;
  /** Whether this welcome is a client-side placeholder (no agent message yet). */
  synthetic: boolean;
}

export interface MessageItem extends ItemBase {
  kind: 'message';
  /** What to display (may carry the smooth-reveal text instead of the full text). */
  message: ChatMessage;
  /** The message as stored in `messages` (for feedback ids, receipts, audio). */
  original: ChatMessage;
  /** Position in the unfiltered `messages` array. */
  originalIndex: number;
  isPrevSameSpeaker: boolean;
  isNextSameSpeaker: boolean;
  /** Last row of the transcript: interactive blocks stay actionable only here. */
  isLast: boolean;
  isLatestQuestion: boolean;
}

export interface FormItem extends ItemBase {
  kind: 'form';
  schema: { message?: string; [k: string]: unknown };
  originalIndex: number;
  isPending: boolean;
}

export type ConversationItem = WelcomeItem | MessageItem | FormItem;

export interface BuildConversationItemsInput {
  messages: ChatMessage[];
  liveTurns: LiveTurnLike[];
  showWelcomeBeforeStart: boolean;
  hasUserMessages: boolean;
  conversationId: string | null | undefined;
  welcomeTitle?: string | null;
  welcomeImageUrl?: string | null;
  welcomeMessage?: string | null;
  shouldTriggerStartForm: boolean;
  revealingMessage: ChatMessage | null;
  revealedText: string;
  dividerBeforeKey: string | null | undefined;
  latestQuestion?: ChatMessage;
  /** Parse (and localize) a form_request message; null when it is not a valid form. */
  parseForm: (message: ChatMessage) => FormItem['schema'] | null;
  isFormAnswered: (originalIndex: number) => boolean;
  /** Current time in epoch seconds (injectable for tests). */
  nowSec?: number;
}

/** Gap after which a new time separator is shown between consecutive messages. */
export const TIME_SEPARATOR_GAP_SEC = 15 * 60;

const toSeconds = (t: number): number => (t > 1e12 ? Math.floor(t / 1000) : t);

const isSameDay = (a: number, b: number): boolean =>
  new Date(a * 1000).toDateString() === new Date(b * 1000).toDateString();

/**
 * Split a welcome message into a headline + body, the same way the default widget's
 * WelcomeCard does: an explicit title wins, otherwise the first sentence becomes it.
 */
export function splitWelcome(text: string, titleProp?: string | null): { title: string; content: string } {
  if (titleProp) return { title: titleProp, content: text };
  const first = (text.split(/[\n.!?]/)[0] || '').trim();
  const rest = text.substring(first.length).trim().replace(/^[,.!?\s]+/, '');
  return { title: first, content: rest };
}

/**
 * Turn the raw transcript into the rows the spotlight conversation renders. Mirrors the
 * display rules of the default widget's renderConversationBody (synthetic welcome, first
 * agent message as welcome, inline forms, live-voice dedupe, smooth reveal), and adds the
 * spotlight-only presentation data: stable keys, grouping and time separators.
 */
export function buildConversationItems(input: BuildConversationItemsInput): ConversationItem[] {
  const {
    messages,
    liveTurns,
    showWelcomeBeforeStart,
    hasUserMessages,
    conversationId,
    welcomeTitle,
    welcomeImageUrl,
    welcomeMessage,
    shouldTriggerStartForm,
    revealingMessage,
    revealedText,
    dividerBeforeKey,
    latestQuestion,
    parseForm,
    isFormAnswered,
  } = input;
  const now = input.nowSec ?? Math.floor(Date.now() / 1000);

  const items: ConversationItem[] = [];
  const usedKeys: Record<string, number> = {};
  const uniqueKey = (base: string): string => {
    const n = usedKeys[base] ?? 0;
    usedKeys[base] = n + 1;
    return n === 0 ? base : `${base}#${n}`;
  };

  const hasWelcomeContent = Boolean(welcomeTitle) || Boolean(welcomeImageUrl) || Boolean(welcomeMessage);
  const firstIsAgent = messages.length > 0 && messages[0].speaker === 'agent';

  if (showWelcomeBeforeStart && !hasUserMessages && !firstIsAgent && hasWelcomeContent && conversationId) {
    const { title, content } = splitWelcome(welcomeMessage || '', welcomeTitle);
    items.push({
      kind: 'welcome',
      key: '__welcome__',
      title,
      content,
      imageUrl: welcomeImageUrl || undefined,
      synthetic: true,
      showNewDivider: false,
      timeSeparator: now,
    });
  }

  // Live-voice turns are rendered locally; their persisted copies are suppressed so a
  // turn never shows twice.
  const liveTurnKeys: Record<string, true> = {};
  for (const turn of liveTurns) {
    if (turn.user.trim()) liveTurnKeys[`customer:${turn.user.trim()}`] = true;
    if (turn.agent.trim()) liveTurnKeys[`agent:${turn.agent.trim()}`] = true;
  }

  const visible: Array<{ message: ChatMessage; originalIndex: number }> = [];
  messages.forEach((message, originalIndex) => {
    if (message.type === 'file') return;
    if (liveTurnKeys[`${message.speaker}:${(message.text || '').trim()}`]) return;
    visible.push({ message, originalIndex });
  });

  let firstAgentVisible = -1;
  for (let i = 0; i < visible.length; i++) {
    if (visible[i].message.speaker === 'agent') {
      firstAgentVisible = i;
      break;
    }
  }

  let prevTime: number | null = items.length > 0 ? now : null;

  visible.forEach(({ message, originalIndex }, i) => {
    const key = uniqueKey(
      message.client_id ? `c:${message.client_id}` : `${message.speaker}:${messageIdentityKey(message)}`,
    );
    const showNewDivider = !!dividerBeforeKey && messageIdentityKey(message) === dividerBeforeKey;

    let timeSeparator: number | undefined;
    const time = message.create_time ? toSeconds(message.create_time) : 0;
    if (time > 0 && message.speaker !== 'special') {
      if (prevTime === null || time - prevTime >= TIME_SEPARATOR_GAP_SEC || !isSameDay(time, prevTime)) {
        timeSeparator = time;
      }
      prevTime = time;
    }

    if (message.type === 'form_request' && message.speaker === 'agent') {
      const schema = parseForm(message);
      if (schema) {
        items.push({
          kind: 'form',
          key,
          schema,
          originalIndex,
          isPending: !isFormAnswered(originalIndex),
          showNewDivider,
          timeSeparator,
        });
        return;
      }
    }

    const isFirstAgentMessage =
      i === firstAgentVisible && message.speaker === 'agent' && !hasUserMessages && !shouldTriggerStartForm;

    if (isFirstAgentMessage && message.type !== 'audio') {
      const text = welcomeMessage || (message === revealingMessage ? revealedText : message.text);
      const { title, content } = splitWelcome(text, welcomeTitle);
      items.push({
        kind: 'welcome',
        key,
        title,
        content,
        imageUrl: welcomeImageUrl || undefined,
        synthetic: false,
        showNewDivider,
        timeSeparator,
      });
      return;
    }

    const display = message === revealingMessage ? { ...message, text: revealedText } : message;
    const prev = visible[i - 1]?.message;
    const next = visible[i + 1]?.message;
    items.push({
      kind: 'message',
      key,
      message: display,
      original: message,
      originalIndex,
      isPrevSameSpeaker: !!prev && prev.speaker === message.speaker && timeSeparator === undefined,
      isNextSameSpeaker: !!next && next.speaker === message.speaker,
      isLast: i === visible.length - 1,
      isLatestQuestion: message === latestQuestion,
      showNewDivider,
      timeSeparator,
    });
  });

  return items;
}
