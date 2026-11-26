import React, { useEffect, useMemo, useRef } from 'react';
import DynamicFormMessage from '../DynamicFormMessage';
import { MarkdownMessage } from '../MarkdownMessage';
import { formatTimestamp } from '../../utils/time';
import type { ChatMessage } from '../../types';
import { buildConversationItems, ConversationItem, FormItem, WelcomeItem } from './conversationItems';
import { RowShell, SpotlightMessage } from './SpotlightMessage';
import type { SpotlightController } from './types';

/** More rows than this arriving at once is a history load, not a live message: no animation. */
const MAX_ANIMATED_BATCH = 3;

/** "2:12 PM" for today, otherwise the default widget's "Yesterday, 2:12 PM" / date form. */
function formatSeparator(epochSec: number, ctl: SpotlightController): string {
  const date = new Date(epochSec * 1000);
  if (date.toDateString() === new Date().toDateString()) {
    try {
      return date.toLocaleTimeString(ctl.language || undefined, { hour: 'numeric', minute: '2-digit' });
    } catch {
      return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    }
  }
  const time = ctl.translations?.time;
  return formatTimestamp(
    epochSec,
    ctl.language,
    time ? { justNow: time.justNow, today: time.today, yesterday: time.yesterday } : undefined,
  );
}

const WelcomeCard: React.FC<{ ctl: SpotlightController; item: WelcomeItem; animateIn: boolean }> = ({
  ctl,
  item,
  animateIn,
}) => {
  const chips = ctl.possibleQueries;
  const disabled = ctl.isAgentTyping || ctl.isLoading;
  return (
    <RowShell speaker="agent" tight={false} animateIn={animateIn} avatarSrc={ctl.logoSrc} wide>
      <div className="gas-card">
        {(item.imageUrl || item.title || item.content) && (
          <div className="gas-card-hero">
            {item.imageUrl && <img className="gas-card-img" src={item.imageUrl} alt="" />}
            {item.title && <div className="gas-card-title">{item.title}</div>}
            {item.content && (
              <div className="gas-card-body">
                <MarkdownMessage text={item.content} />
              </div>
            )}
          </div>
        )}
        {chips.length > 0 && (
          <div className="gas-chips">
            {chips.map((q, i) => (
              <button
                key={`${q}-${i}`}
                type="button"
                className="gas-chip"
                style={{ ['--i' as string]: i }}
                disabled={disabled}
                onClick={() => ctl.onQueryClick(q)}
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </RowShell>
  );
};

const FormRow: React.FC<{ ctl: SpotlightController; item: FormItem; animateIn: boolean }> = ({ ctl, item, animateIn }) => {
  const { themeParams } = ctl;
  const inline = ctl.formDisplay === 'inline' && item.isPending;
  return (
    <RowShell speaker="agent" tight={false} animateIn={animateIn} avatarSrc={ctl.logoSrc} wide={inline}>
      {inline ? (
        <DynamicFormMessage
          schema={item.schema as any}
          onSubmit={(data) => ctl.onFormSubmit(data, item.originalIndex)}
          onCancel={() => ctl.onFormCancel(item.originalIndex)}
          isSubmitting={ctl.submittingFormIndex === item.originalIndex}
          isSubmitted={false}
          primaryColor={themeParams.primaryColor}
          fontFamily={themeParams.fontFamily}
          backgroundColor={themeParams.backgroundColor}
          textColor={themeParams.textColor}
          borderColor={themeParams.borderColor}
          mutedTextColor={themeParams.mutedTextColor}
          inputBackgroundColor={themeParams.inputBackgroundColor}
          variant="card"
        />
      ) : (
        <div className="gas-agent-text">
          {String(item.schema.message || ctl.t('spotlight.formFallback', 'Please fill the form below.'))}
        </div>
      )}
    </RowShell>
  );
};

/**
 * Before the conversation starts: a small, brand-neutral illustration of a chat (two
 * message bubbles and a typing bubble) drawn in the theme's colours.
 */
const EmptyIllustration: React.FC<{ ctl: SpotlightController }> = ({ ctl }) => (
  <div className="gas-hero">
    <svg className="gas-hero-art" viewBox="0 0 220 150" role="img" aria-hidden="true">
      <g className="gas-art-bubble gas-art-bubble--a">
        <path className="gas-art-card" d="M38 62 L32 80 L56 68 Z" />
        <rect className="gas-art-card" x="30" y="18" width="136" height="52" rx="18" />
        <rect className="gas-art-line" x="46" y="34" width="86" height="8" rx="4" />
        <rect className="gas-art-line gas-art-line--soft" x="46" y="49" width="58" height="8" rx="4" />
      </g>
      <g className="gas-art-bubble gas-art-bubble--b">
        <path className="gas-art-primary" d="M194 118 L202 134 L178 124 Z" />
        <rect className="gas-art-primary" x="68" y="84" width="134" height="44" rx="18" />
        <rect className="gas-art-line-on" x="84" y="96" width="78" height="7" rx="3.5" />
        <rect className="gas-art-line-on gas-art-line--soft" x="84" y="108" width="48" height="7" rx="3.5" />
      </g>
      <g className="gas-art-bubble gas-art-bubble--c">
        <rect className="gas-art-card" x="18" y="92" width="44" height="26" rx="13" />
        <circle className="gas-art-dot" cx="31" cy="105" r="3.2" />
        <circle className="gas-art-dot" cx="40" cy="105" r="3.2" />
        <circle className="gas-art-dot" cx="49" cy="105" r="3.2" />
      </g>
    </svg>
    <div className="gas-hero-title">{ctl.t('spotlight.emptyTitle', 'Start a conversation')}</div>
    <div className="gas-hero-body">{ctl.t('spotlight.emptyBody', 'Ask us anything, we are here to help.')}</div>
  </div>
);

const synthetic = (speaker: 'customer' | 'agent', text: string, createTime: number): ChatMessage => ({
  create_time: createTime,
  start_time: 0,
  end_time: 0.01,
  speaker,
  text,
});

export const SpotlightConversation: React.FC<{ ctl: SpotlightController }> = ({ ctl }) => {
  const items = useMemo<ConversationItem[]>(
    () =>
      buildConversationItems({
        messages: ctl.messages,
        liveTurns: ctl.liveTurns,
        showWelcomeBeforeStart: ctl.showWelcomeBeforeStart,
        hasUserMessages: ctl.hasUserMessages,
        conversationId: ctl.conversationId,
        welcomeTitle: ctl.welcomeTitle,
        welcomeImageUrl: ctl.welcomeImageUrl,
        welcomeMessage: ctl.welcomeMessage,
        shouldTriggerStartForm: ctl.shouldTriggerStartForm,
        revealingMessage: ctl.revealingMessage,
        revealedText: ctl.revealedText,
        dividerBeforeKey: ctl.dividerBeforeKey,
        latestQuestion: ctl.latestQuestion,
        parseForm: ctl.parseForm,
        isFormAnswered: ctl.isFormAnswered,
      }),
    // parseForm / isFormAnswered are recreated each render; what they read is covered below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      ctl.messages,
      ctl.liveTurns,
      ctl.showWelcomeBeforeStart,
      ctl.hasUserMessages,
      ctl.conversationId,
      ctl.welcomeTitle,
      ctl.welcomeImageUrl,
      ctl.welcomeMessage,
      ctl.shouldTriggerStartForm,
      ctl.revealingMessage,
      ctl.revealedText,
      ctl.dividerBeforeKey,
      ctl.latestQuestion,
      ctl.language,
      ctl.submittingFormIndex,
    ],
  );

  // Which rows are new enough to animate in. The first paint and bulk history loads are
  // static; a reply that just finished streaming replaces its live row in place, so it
  // does not animate a second time either.
  const seenRef = useRef<Record<string, true> | null>(null);
  const wasStreamingRef = useRef(false);
  const animate: Record<string, boolean> = {};
  if (seenRef.current) {
    const seen = seenRef.current;
    const fresh = items.filter((it) => !seen[it.key]);
    if (fresh.length <= MAX_ANIMATED_BATCH) {
      fresh.forEach((it) => {
        const fromStream = wasStreamingRef.current && it.kind === 'message' && it.message.speaker === 'agent';
        animate[it.key] = !fromStream;
      });
    }
  }
  useEffect(() => {
    const seen = seenRef.current ?? {};
    items.forEach((it) => {
      seen[it.key] = true;
    });
    seenRef.current = seen;
  }, [items]);
  useEffect(() => {
    if (ctl.liveText) {
      wasStreamingRef.current = true;
      return;
    }
    // Keep the flag for one more commit so the saved reply that replaces the stream sees it.
    const id = setTimeout(() => {
      wasStreamingRef.current = false;
    }, 400);
    return () => clearTimeout(id);
  }, [ctl.liveText]);
  // A reset starts a fresh transcript: its first rows should not animate as a batch.
  useEffect(() => {
    if (!ctl.conversationId) seenRef.current = null;
  }, [ctl.conversationId]);

  // The language picker owns the empty panel when it is shown.
  const showHero =
    !ctl.conversationId && !ctl.isRestoringConversation && items.length === 0 && !ctl.languageSelector;
  const lastItem = items[items.length - 1];
  const lastSpeaker =
    lastItem?.kind === 'message' ? lastItem.message.speaker : lastItem ? 'agent' : undefined;

  return (
    <>
      {showHero && <EmptyIllustration ctl={ctl} />}

      {items.map((item) => {
        const animateIn = Boolean(animate[item.key]);
        return (
          <React.Fragment key={item.key}>
            {item.timeSeparator !== undefined && (
              <div className="gas-time" role="separator">
                {formatSeparator(item.timeSeparator, ctl)}
              </div>
            )}
            {item.showNewDivider && (
              <div className="gas-new-pill">{ctl.t('receipts.newMessages', 'New messages')}</div>
            )}
            {item.kind === 'welcome' ? (
              <WelcomeCard ctl={ctl} item={item} animateIn={animateIn} />
            ) : item.kind === 'form' ? (
              <FormRow ctl={ctl} item={item} animateIn={animateIn} />
            ) : (
              <SpotlightMessage
                ctl={ctl}
                message={item.message}
                original={item.original}
                tight={item.isPrevSameSpeaker}
                animateIn={animateIn}
                actionable={item.isLast && item.message.speaker === 'agent'}
                receipt={item.originalIndex === ctl.lastCustomerIndex ? ctl.lastCustomerReceipt : undefined}
                isLatestQuestion={item.isLatestQuestion}
                typeIn={animateIn && item.message.speaker === 'agent'}
              />
            )}
          </React.Fragment>
        );
      })}

      {/* Reply streaming in: an agent row that grows in place. */}
      {ctl.liveText && (
        <SpotlightMessage
          key="__streaming__"
          ctl={ctl}
          message={synthetic('agent', ctl.liveText, ctl.streamingCreateTime || 0)}
          tight={lastSpeaker === 'agent'}
          animateIn
          noFeedback
        />
      )}

      {/* Waiting for the first token: the agent's own thinking phrase when it has some,
          otherwise bouncing dots. */}
      {ctl.isAgentTyping && !ctl.liveText && (
        <div className="gas-typing" role="status" aria-live="polite">
          <img className="gas-typing-avatar" src={ctl.logoSrc} alt="" aria-hidden="true" />
          {ctl.customThinkingLabel ? (
            <span key={ctl.customThinkingLabel} className="gas-thinking">
              {ctl.customThinkingLabel}
            </span>
          ) : (
            <span className="gas-dots" aria-label={ctl.t('spotlight.typing', 'Typing')}>
              <span />
              <span />
              <span />
            </span>
          )}
        </div>
      )}

      {/* Live-voice turns (kept locally; their persisted copies are filtered out above). */}
      {ctl.liveTurns.map((turn, i) => (
        <React.Fragment key={`live-${i}`}>
          {turn.user.trim() !== '' && (
            <SpotlightMessage ctl={ctl} message={synthetic('customer', turn.user, turn.createTime)} tight={false} animateIn noFeedback />
          )}
          {turn.agent.trim() !== '' && (
            <SpotlightMessage ctl={ctl} message={synthetic('agent', turn.agent, turn.createTime)} tight={false} animateIn noFeedback />
          )}
        </React.Fragment>
      ))}
      {ctl.liveVoiceActive && ctl.liveCaption.user.trim() !== '' && (
        <SpotlightMessage
          key="__live_user__"
          ctl={ctl}
          message={synthetic('customer', ctl.liveCaption.user, ctl.liveCaption.createTime)}
          tight={false}
          animateIn
          noFeedback
        />
      )}
      {ctl.liveVoiceActive && ctl.liveCaption.agent.trim() !== '' && (
        <SpotlightMessage
          key="__live_agent__"
          ctl={ctl}
          message={synthetic('agent', ctl.liveCaption.agent, ctl.liveCaption.createTime)}
          tight={false}
          animateIn
          noFeedback
        />
      )}
    </>
  );
};
