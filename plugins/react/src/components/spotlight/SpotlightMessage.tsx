import React, { useMemo, useRef, useState } from 'react';
import { AlertCircle, Check, CheckCheck, Mic, RotateCcw, ThumbsDown, ThumbsUp, User, UserX } from 'lucide-react';
import type { ChatMessage, MessageReceiptStatus } from '../../types';
import { InteractiveContent } from '../InteractiveContent';
import { AudioPlayer } from '../AudioPlayer';
import { SpotlightAttachments } from './SpotlightAttachments';
import { withoutOptionSeparators } from './typing';
import { useTypingReveal } from './useTypingReveal';
import { MarkdownMessage } from '../MarkdownMessage';
import { parseInteractiveContentBlocks } from '../../utils/interactiveContent';
import { LATEST_QUESTION_ATTR } from '../../hooks/useScrollManagement';
import type { SpotlightController } from './types';
import { SPOTLIGHT_MARKDOWN } from './CodeBlock';

interface RowShellProps {
  speaker: 'customer' | 'agent';
  tight: boolean;
  animateIn: boolean;
  avatarSrc?: string;
  showAvatar?: boolean;
  isLatestQuestion?: boolean;
  /** Let the body take the full row width (cards, forms). */
  wide?: boolean;
  children: React.ReactNode;
}

/**
 * One transcript row. Agent rows carry a small avatar (only on the first row of a run)
 * and no bubble; visitor rows are a right-aligned bubble. `animateIn` is captured at
 * mount so a row animates exactly once, and only when it is genuinely new.
 */
export const RowShell: React.FC<RowShellProps> = ({
  speaker,
  tight,
  animateIn,
  avatarSrc,
  showAvatar = true,
  isLatestQuestion,
  wide = false,
  children,
}) => {
  const [animate] = useState(animateIn);
  const isUser = speaker === 'customer';
  const className = [
    'gas-row',
    isUser ? 'gas-row--user' : 'gas-row--agent',
    tight ? 'gas-row--tight' : '',
    animate ? 'gas-row--in' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={className} {...(isLatestQuestion ? { [LATEST_QUESTION_ATTR]: true } : {})}>
      {!isUser && avatarSrc && (
        <img
          className={`gas-row-avatar${showAvatar ? '' : ' gas-row-avatar--spacer'}`}
          src={avatarSrc}
          alt=""
          aria-hidden="true"
        />
      )}
      <div className={`gas-row-body${wide ? ' gas-row-body--wide' : ''}`}>{children}</div>
    </div>
  );
};

/** Takeover / offline / system notices: a centred pill. */
export const SpecialNotice: React.FC<{ message: ChatMessage; t: SpotlightController['t'] }> = ({ message, t }) => {
  const text = message.text.toLowerCase();
  const isWarn =
    Boolean(message.notice) ||
    text.includes('offline') ||
    text.includes('inactive') ||
    text.includes('unavailable') ||
    Boolean(message.linkUrl && message.linkLabel);
  const icon = isWarn ? (
    <AlertCircle size={15} />
  ) : text.includes('took over') || text.includes('takeover') ? (
    <UserX size={15} />
  ) : (
    <User size={15} />
  );
  return (
    <div className={`gas-special${isWarn ? ' gas-special--warn' : ''}`} role="status">
      {icon}
      <span>
        {message.notice === 'reply_failed' ? t('sendFailure.replyFailed', message.text) : message.text}
        {message.linkUrl && message.linkLabel && (
          <>
            {' '}
            <a href={message.linkUrl} target="_blank" rel="noopener noreferrer">
              {message.linkLabel}
            </a>
          </>
        )}
      </span>
    </div>
  );
};

interface SpotlightMessageProps {
  ctl: SpotlightController;
  message: ChatMessage;
  /** The stored message (feedback ids); defaults to `message`. */
  original?: ChatMessage;
  tight: boolean;
  animateIn: boolean;
  /** Interactive blocks (quick options, item pickers) only act on the newest row. Once a
   *  newer message exists the agent's suggested ***questions*** are removed, not disabled. */
  actionable?: boolean;
  receipt?: MessageReceiptStatus;
  isLatestQuestion?: boolean;
  /** Hide the thumbs row (live-voice and streaming rows have nothing to rate yet). */
  noFeedback?: boolean;
  /** Type the reply out instead of showing it whole (an agent reply that just arrived
   *  without streaming). Read once, when the row mounts. */
  typeIn?: boolean;
}

export const SpotlightMessage: React.FC<SpotlightMessageProps> = ({
  ctl,
  message,
  original,
  tight,
  animateIn,
  actionable = false,
  receipt,
  isLatestQuestion,
  noFeedback = false,
  typeIn = false,
}) => {
  const { t, themeParams } = ctl;
  const isUser = message.speaker === 'customer';
  const blocks = useMemo(
    () =>
      parseInteractiveContentBlocks(message.text, message.type as 'file' | 'message' | undefined, {
        keepUnknownJson: true,
      }),
    [message.text, message.type],
  );

  // Suggested questions only make sense while they can still be picked: once the visitor
  // has moved on (picked one or typed their own), drop them from older replies.
  const visibleBlocks = useMemo(
    () => withoutOptionSeparators(actionable ? blocks : blocks.filter((b) => b.kind !== 'options')),
    [actionable, blocks],
  );

  // Typing: the reply is laid out whole and revealed by a sweep (see useTypingReveal).
  const isAgentText = message.speaker === 'agent' && message.type !== 'audio';
  const agentTextRef = useRef<HTMLDivElement>(null);
  const { typing } = useTypingReveal(agentTextRef, typeIn && isAgentText);

  if (message.speaker === 'special') return <SpecialNotice message={message} t={ctl.t} />;
  // A reply that consisted only of suggestions leaves nothing to show once they are gone.
  if (!isUser && message.type !== 'audio' && visibleBlocks.length === 0 && !message.attachments?.length) {
    return null;
  }

  const source = original ?? message;
  const feedbackValue = source.feedback?.length ? source.feedback[source.feedback.length - 1].feedback : undefined;
  const feedbackId = source.message_id || (source as unknown as { id?: string }).id;
  const audioProps = {
    primaryColor: themeParams.primaryColor,
    backgroundColor: themeParams.backgroundColor,
    mutedTextColor: themeParams.mutedTextColor,
    trackColor: themeParams.borderColor,
  };

  let body: React.ReactNode = null;
  if (message.type === 'audio') {
    if (isUser && message.audioObjectUrl) {
      body = <AudioPlayer blobUrl={message.audioObjectUrl} {...audioProps} />;
    } else if (message.message_id && ctl.useAudio) {
      body = (
        <AudioPlayer
          audioUrl={ctl.audioUrlBuilder(message.message_id)}
          headers={ctl.audioHeaders}
          autoPlay={!isUser && ctl.autoPlayAudioMessageId === message.message_id}
          {...audioProps}
        />
      );
    } else {
      body = (
        <div className={isUser ? 'gas-bubble' : 'gas-agent-text'} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Mic size={15} />
          <span>{message.text || (isUser ? '[Voice message]' : '[Audio response]')}</span>
        </div>
      );
    }
  } else if (message.text) {
    body = isUser ? (
      <div className="gas-bubble">
        <MarkdownMessage text={message.text} />
      </div>
    ) : (
      <div
        ref={agentTextRef}
        className={`gas-agent-text${typing ? ' gas-agent-text--typing' : ''}`}
        aria-busy={typing || undefined}
      >
        <InteractiveContent
          blocks={visibleBlocks}
          primaryColor={themeParams.primaryColor}
          textColor={themeParams.textColor}
          cardBackgroundColor={themeParams.backgroundColor}
          borderColor={themeParams.borderColor}
          mutedTextColor={themeParams.mutedTextColor}
          isActionable={actionable && !ctl.isAgentTyping}
          onQuickAction={ctl.onQuickAction}
          onScheduleConfirm={ctl.onScheduleConfirm}
          markdownComponents={SPOTLIGHT_MARKDOWN}
        />
      </div>
    );
  }

  return (
    <RowShell
      speaker={isUser ? 'customer' : 'agent'}
      tight={tight}
      animateIn={animateIn}
      avatarSrc={ctl.logoSrc}
      showAvatar={!tight}
      isLatestQuestion={isLatestQuestion}
    >
      {message.attachments && message.attachments.length > 0 && (
        <SpotlightAttachments
          ctl={ctl}
          attachments={message.attachments}
          align={isUser ? 'end' : 'start'}
          spaced={Boolean(message.text)}
        />
      )}

      {body}

      {!isUser && !noFeedback && !typing && feedbackId && (
        <div className={`gas-feedback${feedbackValue ? ' gas-feedback--set' : ''}`}>
          {(!feedbackValue || feedbackValue === 'good') && (
            <button
              type="button"
              className={`gas-feedback-btn${feedbackValue === 'good' ? ' gas-feedback-btn--on' : ''}`}
              title={t('feedback.thumbsUp', 'Thumbs up')}
              aria-label={t('feedback.thumbsUp', 'Thumbs up')}
              aria-pressed={feedbackValue === 'good'}
              disabled={Boolean(feedbackValue)}
              onClick={() => ctl.onFeedback(feedbackId, 'good')}
            >
              <ThumbsUp size={15} />
            </button>
          )}
          {(!feedbackValue || feedbackValue === 'bad') && (
            <button
              type="button"
              className={`gas-feedback-btn${feedbackValue === 'bad' ? ' gas-feedback-btn--on' : ''}`}
              title={t('feedback.thumbsDown', 'Thumbs down')}
              aria-label={t('feedback.thumbsDown', 'Thumbs down')}
              aria-pressed={feedbackValue === 'bad'}
              disabled={Boolean(feedbackValue)}
              onClick={() => ctl.onFeedback(feedbackId, 'bad')}
            >
              <ThumbsDown size={15} />
            </button>
          )}
        </div>
      )}

      {isUser && message.send_failed && (
        <span className="gas-receipt gas-receipt--failed" role="status">
          <AlertCircle size={12} />
          {t('sendFailure.notDelivered', 'Not delivered')}
          {ctl.canRetry(message) && (
            <>
              <span aria-hidden="true">·</span>
              <button type="button" className="gas-retry" onClick={() => ctl.onRetry(message)}>
                <RotateCcw size={11} />
                {t('sendFailure.retry', 'Retry')}
              </button>
            </>
          )}
        </span>
      )}

      {isUser && receipt && !message.send_failed && (
        <span className={`gas-receipt${receipt === 'seen' ? ' gas-receipt--seen' : ''}`}>
          {receipt === 'sent' ? <Check size={12} /> : <CheckCheck size={12} />}
          {t(`receipts.${receipt}`, receipt.charAt(0).toUpperCase() + receipt.slice(1))}
        </span>
      )}
    </RowShell>
  );
};
