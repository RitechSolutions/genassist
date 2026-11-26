import React, { useState } from 'react';
import { ArrowUp, MessageCircle, Sparkles, X } from 'lucide-react';
import { MarkdownMessage } from '../MarkdownMessage';
import { splitWelcome } from './conversationItems';
import type { SpotlightController } from './types';

const LAUNCHER = 58;
const GAP = 14;
const MAX_TEASER_CHIPS = 3;

/**
 * Closed state: the round launcher, plus (when the host opts into `quickInput`) a teaser
 * card above it — agent pill, greeting, suggested questions and a quick reply input — so
 * a visitor can start without opening the full panel.
 */
export const SpotlightLauncher: React.FC<{ ctl: SpotlightController }> = ({ ctl }) => {
  const { t } = ctl;
  const [draft, setDraft] = useState('');
  const isLeft = ctl.position.endsWith('left');
  const isTop = ctl.position.startsWith('top');
  const hSide = isLeft ? 'left' : 'right';
  const vSide = isTop ? 'top' : 'bottom';
  // Bottom-docked, the launcher and its quick input ride on the keyboard while it is up.
  const edge = isTop ? ctl.offsetY : ctl.offsetY + ctl.keyboard.inset;
  const openLabel = t('spotlight.open', 'Open chat');

  const icon =
    ctl.chatBubbleIcon === 'message' ? (
      <MessageCircle size={26} />
    ) : ctl.chatBubbleIcon === 'x' ? (
      <X size={24} />
    ) : (
      <Sparkles size={24} />
    );

  // The teaser greets only a fresh conversation; mid-conversation it is just a reply box.
  const greet = !ctl.hasUserMessages;
  const welcome = splitWelcome(ctl.welcomeMessage || '', ctl.welcomeTitle);
  const title = welcome.title || t('spotlight.teaserTitle', 'Hi there!');
  const body = welcome.title ? welcome.content : t('spotlight.teaserBody', 'How can we help you today?');
  const chips = greet ? ctl.possibleQueries.slice(0, MAX_TEASER_CHIPS) : [];
  // Mid-conversation with unread replies: preview the newest one.
  let preview: string | null = null;
  if (!greet && ctl.unreadCount > 0) {
    for (let i = ctl.messages.length - 1; i >= 0; i--) {
      const m = ctl.messages[i];
      if (m.speaker === 'agent' && m.text && m.type !== 'form_request' && m.type !== 'audio' && m.type !== 'file') {
        preview = m.text;
        break;
      }
    }
  }

  const sendDraft = () => {
    const text = draft.trim();
    if (!text) return;
    setDraft('');
    ctl.onQuickInputSend(text);
  };

  const teaserWidth = Math.min(340, Math.max(240, ctl.windowWidth - ctl.offsetX * 2));

  return (
    <>
      {ctl.showQuickInput && (
        <div
          className="gas-teaser"
          style={{
            position: 'fixed',
            zIndex: 1000,
            [hSide]: ctl.offsetX,
            [vSide]: edge + LAUNCHER + GAP,
            width: teaserWidth,
            ['--gas-origin' as string]: `${vSide} ${hSide}`,
          }}
        >
          <div className="gas-teaser-top">
            <button type="button" className="gas-teaser-pill" onClick={() => ctl.setOpen(true)}>
              {ctl.brandLogo ? (
                <img className="gas-teaser-brand" src={ctl.brandLogo} alt={ctl.headerTitle} />
              ) : (
                <>
                  <img src={ctl.logoSrc} alt="" />
                  <span>{ctl.headerTitle}</span>
                </>
              )}
            </button>
            <button
              type="button"
              className="gas-icon-btn gas-teaser-close"
              onClick={ctl.onDismissQuickInput}
              aria-label={t('spotlight.dismiss', 'Dismiss')}
              title={t('spotlight.dismiss', 'Dismiss')}
            >
              <X size={15} />
            </button>
          </div>

          <div className="gas-teaser-card">
            {greet && (
              <button type="button" className="gas-teaser-hero" onClick={() => ctl.setOpen(true)}>
                <span className="gas-teaser-title">{title}</span>
                {body && (
                  <span className="gas-teaser-body">
                    <MarkdownMessage text={body} />
                  </span>
                )}
              </button>
            )}
            {preview && (
              <button type="button" className="gas-teaser-hero gas-teaser-preview" onClick={() => ctl.setOpen(true)}>
                <span className="gas-teaser-body">
                  <MarkdownMessage text={preview} />
                </span>
              </button>
            )}
            {chips.length > 0 && (
              <div className="gas-chips gas-teaser-chips">
                {chips.map((q, i) => (
                  <button
                    key={`${q}-${i}`}
                    type="button"
                    className="gas-chip"
                    style={{ ['--i' as string]: i + 2 }}
                    onClick={() => {
                      ctl.setOpen(true);
                      ctl.onQueryClick(q);
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
            <form
              className="gas-teaser-input"
              onSubmit={(e) => {
                e.preventDefault();
                sendDraft();
              }}
            >
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={t('spotlight.writeMessage', 'Write a message…')}
                aria-label={t('spotlight.writeMessage', 'Write a message…')}
              />
              <button
                type="submit"
                className="gas-send"
                disabled={!draft.trim()}
                aria-label={t('spotlight.send', 'Send message')}
                title={t('spotlight.send', 'Send message')}
              >
                <ArrowUp size={17} strokeWidth={2.6} />
              </button>
            </form>
          </div>
        </div>
      )}

      <button
        type="button"
        className={`gas-launcher${ctl.unreadCount > 0 ? ' gas-launcher--unread' : ''}`}
        style={{ position: 'fixed', zIndex: 1000, [hSide]: ctl.offsetX, [vSide]: edge }}
        onClick={() => ctl.setOpen(true)}
        aria-label={openLabel}
        title={openLabel}
      >
        {icon}
        {ctl.unreadCount > 0 && (
          <span className="gas-launcher-badge" aria-label={`${ctl.unreadCount} unread`}>
            {ctl.unreadCount > 99 ? '99+' : ctl.unreadCount}
          </span>
        )}
      </button>
    </>
  );
};
