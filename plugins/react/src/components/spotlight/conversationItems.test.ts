import { describe, expect, it } from 'vitest';
import type { ChatMessage } from '../../types';
import {
  buildConversationItems,
  BuildConversationItemsInput,
  splitWelcome,
  TIME_SEPARATOR_GAP_SEC,
} from './conversationItems';

const T0 = 1_764_000_000; // fixed epoch seconds

const msg = (speaker: ChatMessage['speaker'], text: string, t: number, extra: Partial<ChatMessage> = {}): ChatMessage => ({
  create_time: t,
  start_time: 0,
  end_time: 0,
  speaker,
  text,
  ...extra,
});

const base = (overrides: Partial<BuildConversationItemsInput> = {}): BuildConversationItemsInput => ({
  messages: [],
  liveTurns: [],
  showWelcomeBeforeStart: true,
  hasUserMessages: false,
  conversationId: 'c1',
  welcomeTitle: null,
  welcomeImageUrl: null,
  welcomeMessage: null,
  shouldTriggerStartForm: false,
  revealingMessage: null,
  revealedText: '',
  dividerBeforeKey: null,
  parseForm: (m) => {
    try {
      return JSON.parse(m.text);
    } catch {
      return null;
    }
  },
  isFormAnswered: () => false,
  nowSec: T0,
  ...overrides,
});

describe('splitWelcome', () => {
  it('uses the explicit title and keeps the full text as body', () => {
    expect(splitWelcome('Hi there. How can I help?', 'Welcome')).toEqual({
      title: 'Welcome',
      content: 'Hi there. How can I help?',
    });
  });

  it('turns the first sentence into the title when none is given', () => {
    expect(splitWelcome('Hello! Still having questions?')).toEqual({
      title: 'Hello',
      content: 'Still having questions?',
    });
  });
});

describe('buildConversationItems', () => {
  it('shows a synthetic welcome only when there is welcome content and a conversation', () => {
    expect(buildConversationItems(base({ welcomeMessage: 'Hello! Ask me anything.' }))).toMatchObject([
      { kind: 'welcome', synthetic: true, title: 'Hello', content: 'Ask me anything.' },
    ]);
    expect(buildConversationItems(base({ welcomeMessage: 'Hello!', conversationId: null }))).toEqual([]);
    expect(buildConversationItems(base())).toEqual([]);
  });

  it('renders the first agent message as the welcome card until the visitor speaks', () => {
    const before = buildConversationItems(base({ messages: [msg('agent', 'Hi! I am the bot.', T0)] }));
    expect(before).toMatchObject([{ kind: 'welcome', synthetic: false, title: 'Hi', content: 'I am the bot.' }]);

    const after = buildConversationItems(
      base({ hasUserMessages: true, messages: [msg('agent', 'Hi! I am the bot.', T0), msg('customer', 'yo', T0 + 5)] }),
    );
    expect(after.map((i) => i.kind)).toEqual(['message', 'message']);
  });

  it('keeps a row key stable when the server id arrives for an optimistic message', () => {
    const optimistic = msg('customer', 'hello', T0, { client_id: 'abc' });
    const confirmed = { ...optimistic, message_id: 'srv-1', sequence_number: 3 };
    const a = buildConversationItems(base({ hasUserMessages: true, messages: [optimistic] }));
    const b = buildConversationItems(base({ hasUserMessages: true, messages: [confirmed] }));
    expect(a[0].key).toBe(b[0].key);
  });

  it('de-duplicates keys for messages that share an identity', () => {
    const items = buildConversationItems(
      base({ hasUserMessages: true, messages: [msg('customer', 'a', T0), msg('customer', 'b', T0)] }),
    );
    expect(new Set(items.map((i) => i.key)).size).toBe(2);
  });

  it('adds a time separator at the start and after a long gap, and groups same-speaker runs', () => {
    const items = buildConversationItems(
      base({
        hasUserMessages: true,
        messages: [
          msg('customer', 'q1', T0),
          msg('customer', 'q2', T0 + 10),
          msg('agent', 'a1', T0 + 20),
          msg('agent', 'a2', T0 + 20 + TIME_SEPARATOR_GAP_SEC),
        ],
      }),
    );
    expect(items.map((i) => i.timeSeparator)).toEqual([T0, undefined, undefined, T0 + 20 + TIME_SEPARATOR_GAP_SEC]);
    const rows = items.filter((i) => i.kind === 'message');
    // q2 continues q1's run; a2 starts a new run because a separator sits between them.
    expect(rows.map((r) => (r.kind === 'message' ? r.isPrevSameSpeaker : null))).toEqual([false, true, false, false]);
    expect(rows.map((r) => (r.kind === 'message' ? r.isLast : null))).toEqual([false, false, false, true]);
  });

  it('drops file messages and persisted copies of live-voice turns', () => {
    const items = buildConversationItems(
      base({
        hasUserMessages: true,
        liveTurns: [{ user: 'spoken', agent: 'answered', createTime: T0 }],
        messages: [
          msg('customer', 'typed', T0),
          msg('customer', 'file.pdf', T0 + 1, { type: 'file' }),
          msg('customer', 'spoken', T0 + 2),
          msg('agent', 'answered', T0 + 3),
        ],
      }),
    );
    expect(items.map((i) => (i.kind === 'message' ? i.message.text : i.kind))).toEqual(['typed']);
  });

  it('turns form requests into form items with their pending state', () => {
    const form = msg('agent', JSON.stringify({ message: 'Fill me', fields: [] }), T0 + 1, { type: 'form_request' });
    const items = buildConversationItems(
      base({
        hasUserMessages: true,
        messages: [msg('customer', 'hi', T0), form],
        isFormAnswered: (i) => i !== 1,
      }),
    );
    expect(items[1]).toMatchObject({ kind: 'form', originalIndex: 1, isPending: true, schema: { message: 'Fill me' } });
  });

  it('shows revealed text for the message being smoothly revealed and marks the new-message divider', () => {
    const reply = msg('agent', 'full reply text', T0 + 2, { message_id: 'm2' });
    const items = buildConversationItems(
      base({
        hasUserMessages: true,
        messages: [msg('customer', 'q', T0), reply],
        revealingMessage: reply,
        revealedText: 'full re',
        dividerBeforeKey: 'm2',
      }),
    );
    expect(items[1]).toMatchObject({ kind: 'message', showNewDivider: true, message: { text: 'full re' } });
    expect(items[1].kind === 'message' && items[1].original.text).toBe('full reply text');
  });

  it('never gives a special notice its own time separator', () => {
    const items = buildConversationItems(
      base({ hasUserMessages: true, messages: [msg('special', 'Agent took over', T0)] }),
    );
    expect(items[0].timeSeparator).toBeUndefined();
  });
});
