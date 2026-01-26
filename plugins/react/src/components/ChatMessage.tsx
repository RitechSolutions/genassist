import React from 'react';
import { WelcomeCard } from './WelcomeCard';
import { ChatMessage, ScheduleItem, Translations } from '../types';
import { User, UserX, AlertCircle, ThumbsUp, ThumbsDown } from 'lucide-react';
import { formatTimestamp } from '../utils/time';
import { getFileIcon } from './FileTypeIcon';
import { InteractiveContent } from './InteractiveContent';
import { parseInteractiveContentBlocks } from '../utils/interactiveContent';
import { defaultTranslations, getTranslationString, mergeTranslations } from '../utils/i18n';
export { AttachmentPreview } from './AttachmentPreview';

interface ChatMessageProps {
  message: ChatMessage;
  theme?: {
    primaryColor?: string;
    secondaryColor?: string;
    fontFamily?: string;
    fontSize?: string;
    backgroundColor?: string;
    textColor?: string;
  };
  onPlayAudio?: (text: string) => Promise<void>;
  isPlayingAudio?: boolean;
  isFirstMessage?: boolean;
  isNextSameSpeaker?: boolean;
  isPrevSameSpeaker?: boolean;
  onFeedback?: (messageId: string, value: 'good' | 'bad') => void;
  enableTypewriter?: boolean;
  welcomeImageUrl?: string;
  welcomeTitle?: string;
  possibleQueries?: string[];
  onQuickQuery?: (query: string) => void;
  isLastMessage?: boolean;
  onQuickAction?: (text: string) => void;
  onScheduleConfirm?: (schedule: ScheduleItem) => void;
  translations?: Translations;
  language?: string;
  agentName?: string; // Custom agent name to display instead of translation
  isAgentTyping?: boolean; // Whether agent is currently typing/thinking
}

export const ChatMessageComponent: React.FC<ChatMessageProps> = ({
  message,
  theme,
  onPlayAudio,
  isFirstMessage = false,
  isPrevSameSpeaker = false,
  onFeedback,
  welcomeImageUrl,
  welcomeTitle: welcomeTitleProp,
  possibleQueries,
  onQuickQuery,
  isLastMessage = false,
  onQuickAction,
  onScheduleConfirm,
  translations: customTranslations,
  language,
  agentName,
  isAgentTyping = false,
}) => {
  // Merge translations with defaults
  const translations = React.useMemo(
    () => mergeTranslations(customTranslations, defaultTranslations),
    [customTranslations]
  );

  // Translation helper
  const t = (key: string, fallback?: string): string => {
    return getTranslationString(key, translations, fallback);
  };
  const isUser = message.speaker === 'customer';
  const isSpecial = message.speaker === 'special';
  const isWelcomeMessage = !isUser && !isSpecial && isFirstMessage;
  const [isHovered, setIsHovered] = React.useState(false);
  const [editingFeedback] = React.useState(false);
  const [displayText] = React.useState<string>(message.text);
  const contentBlocks = React.useMemo(
    () => parseInteractiveContentBlocks(displayText),
    [displayText]
  );

  // Format timestamp with translations
  const timestamp = React.useMemo(() => {
    const timeTranslations = translations?.time ? {
      justNow: translations.time.justNow,
      today: translations.time.today,
      yesterday: translations.time.yesterday,
    } : undefined;
    return formatTimestamp(message.create_time, language, timeTranslations);
  }, [message.create_time, language, translations]);

  // Fast typewriter effect for newly displayed agent messages, fix later
  // React.useEffect(() => {
  //   if (!isUser && !isSpecial && enableTypewriter && message.text !== lastAnimatedRef.current) {
  //     lastAnimatedRef.current = message.text;
  //     setIsTypewriting(true);
  //     setDisplayText('');
  //     let i = 0;
  //     const total = message.text.length;
  //     const tickMs = 16;
  //     const targetMs = 1200;
  //     const charsPerTick = Math.max(1, Math.round(total / (targetMs / tickMs)));
  //     const interval = window.setInterval(() => {
  //       i += charsPerTick;
  //       if (i >= total) {
  //         setDisplayText(message.text);
  //         setIsTypewriting(false);
  //         window.clearInterval(interval);
  //       } else {
  //         setDisplayText(message.text.slice(0, i));
  //       }
  //     }, tickMs);
  //     return () => window.clearInterval(interval);
  //   } else {
  //     setDisplayText(message.text);
  //     setIsTypewriting(false);
  //   }
  // }, [message.text, enableTypewriter, isUser, isSpecial]);

  // Updated design colors
  const userBubbleBgColor = '#E4E4E7'; // grey for user
  const userTextColor = '#000000';
  const agentTextColor = theme?.textColor || '#000000';
  const primaryColor = theme?.primaryColor || '#4f46e5';
  const fontFamily = theme?.fontFamily || 'Roboto, Arial, sans-serif';
  const fontSize = theme?.fontSize || '15px';
  const bubbleTextColor = isUser ? userTextColor : agentTextColor;

  const messageContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    marginBottom: isPrevSameSpeaker ? '8px' : '8px',
    marginTop: isPrevSameSpeaker ? '0px' : '16px',
    position: 'relative',
    alignItems: isUser ? 'flex-end' : 'flex-start',
  };

  const labelRowStyle: React.CSSProperties = {
    display: isPrevSameSpeaker ? 'none' : 'flex',
    width: '80%',
    justifyContent: isUser ? 'flex-end' : 'flex-start',
    alignItems: 'baseline',
    gap: '8px',
    marginBottom: '6px',
  };

  const messageLabelStyle: React.CSSProperties = {
    fontSize: '14px',
    color: '#000000',
    lineHeight: 1,
    fontWeight: 600,
  };

  const topTimestampStyle: React.CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
    lineHeight: 1,
  };

  const messageBubbleContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    maxWidth: '80%',
  };

  // Only user's messages should render as bubbles.
  // Agent messages are plain text with no container background.
  const bubbleStyle: React.CSSProperties = isUser
    ? {
        backgroundColor: userBubbleBgColor,
        color: userTextColor,
        padding: '12px 16px',
        borderRadius: '12px 0 12px 12px',
        fontSize,
        fontFamily,
        wordBreak: 'break-word',
        lineHeight: 1.4,
        maxWidth: '100%',
        border: 'none',
        boxShadow: '0 1px 2px rgba(0,0,0,0.08)'
      }
    : {
        backgroundColor: 'transparent',
        color: agentTextColor,
        padding: 0,
        borderRadius: 0,
        fontSize,
        fontFamily,
        wordBreak: 'break-word',
        lineHeight: 1.4,
        maxWidth: '100%',
        border: 'none',
        boxShadow: 'none'
      };

  const attachmentsContainerStyle: React.CSSProperties = {
    marginTop: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  };

  // Feedback state and UI (thumbs up/down) for agent messages
  const feedbackValue = (message.feedback && message.feedback.length > 0)
    ? message.feedback[message.feedback.length - 1].feedback
    : undefined;

  const thumbsShouldShow = !isUser && !isSpecial && isHovered && !feedbackValue;
  const showThumbsArea = !isUser && !isSpecial; // Only agents have thumbs area

  const feedbackRowStyle: React.CSSProperties = {
    display: showThumbsArea ? 'flex' : 'none',
    marginTop: 8,
    alignSelf: 'flex-start',
    alignItems: 'center',
    height: 20,
    gap: 8,
    visibility: thumbsShouldShow || !!feedbackValue ? 'visible' : 'hidden',
  };

  const iconButtonStyle: React.CSSProperties = {
    background: 'transparent',
    border: 'none',
    padding: 0,
    cursor: 'pointer',
    color: '#9ca3af',
    display: thumbsShouldShow ? 'flex' : 'none',
    alignItems: 'center',
  };

  const separatorStyle: React.CSSProperties = {
    width: 1,
    height: 14,
    backgroundColor: '#e5e7eb',
    display: thumbsShouldShow ? 'block' : 'none',
  };

  const singleIconStyle: React.CSSProperties = {
    color: '#000000',
    display: feedbackValue ? 'flex' : 'none',
    alignItems: 'center',
  };

  let welcomeTitle = welcomeTitleProp || '';
  let welcomeContent = '';
  
  if (isWelcomeMessage) {
    const messageText = message.text;
    if (!welcomeTitleProp) {
      const parts = messageText.split(/[\n\.!?]/);
      if (parts.length > 0) welcomeTitle = (parts[0] || '').trim();
      welcomeContent = messageText.substring(welcomeTitle.length).trim();
      welcomeContent = welcomeContent.replace(/^[,.!?\s]+/, '');
    } else {
      welcomeContent = messageText;
    }
  }

  // Handle special messages (like takeover indicators)
  if (isSpecial) {
    const specialMessageStyle: React.CSSProperties = {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      margin: '16px 0',
      width: '100%',
    };

    // Determine icon and style based on message content
    let icon;
    let backgroundColor = '#E3F2FD';
    let textColor = '#1976D2';
    
    if (message.text.toLowerCase().includes('offline') || message.text.toLowerCase().includes('inactive')) {
      icon = <AlertCircle size={18} />;
      backgroundColor = '#FFF3E0';
      textColor = '#F57C00';
    } else if (message.text.toLowerCase().includes('took over') || message.text.toLowerCase().includes('takeover')) {
      icon = <UserX size={18} />;
    } else {
      icon = <User size={18} />;
    }

    const specialBubbleStyle: React.CSSProperties = {
      backgroundColor,
      color: textColor,
      padding: '8px 16px',
      borderRadius: '16px',
      fontSize: '14px',
      fontFamily,
      fontWeight: '500',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
    };

    return (
      <div style={specialMessageStyle}>
        <div style={specialBubbleStyle}>
          {icon}
          {message.text}
        </div>
      </div>
    );
  }

  if (isWelcomeMessage) {
    return (
      <div style={messageContainerStyle}>
        <div style={{ ...messageBubbleContainerStyle }}>
          <WelcomeCard
            theme={theme}
            imageUrl={welcomeImageUrl}
            title={welcomeTitle}
            content={welcomeContent}
            possibleQueries={possibleQueries}
            onQuickQuery={onQuickQuery}
            isAgentTyping={isAgentTyping}
          />
        </div>
      </div>
    );
  }

  return (
    <div 
      style={messageContainerStyle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => { if (!editingFeedback) setIsHovered(false); }}
    >
      <div style={labelRowStyle}>
        {isUser ? (
          <>
            <div style={topTimestampStyle}>{timestamp}</div>
            <div style={messageLabelStyle}>{t('labels.you')}</div>
          </>
        ) : (
          <>
            <div style={messageLabelStyle}>{agentName || t('labels.agent')}</div>
            <div style={topTimestampStyle}>{timestamp}</div>
          </>
        )}
      </div>

      {message.attachments && message.attachments.length > 0 && (
        <div style={{ ...attachmentsContainerStyle, alignItems: isUser ? 'flex-end' : 'flex-start' }}>
          {message.attachments.map((attachment, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 14px',
                backgroundColor: isUser ? 'rgba(255,255,255,0.12)' : '#f5f5f5',
                border: isUser ? '1px solid rgba(255,255,255,0.18)' : '1px solid #e5e5e5',
                borderRadius: '12px',
                minWidth: '260px',
                maxWidth: '360px',
                pointerEvents: 'none',
              }}
            >
              {attachment.type.startsWith('image/') ? (
                <img
                  src={attachment.url}
                  alt={attachment.name}
                  style={{ width: 56, height: 56, borderRadius: 8, objectFit: 'cover' }}
                />
              ) : (
                <div style={{ width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {getFileIcon(attachment.type)}
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{attachment.name}</div>
                <div style={{ fontSize: 12, opacity: 0.8 }}>
                  {attachment.type.includes('/') ? attachment.type.split('/')[1].toUpperCase() : attachment.type}
                  {attachment.size ? ` · ${(attachment.size / 1024).toFixed(1)} KB` : ''}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {message.text && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', alignSelf: isUser ? 'flex-end' : 'flex-start' }}>
          <div style={{ ...bubbleStyle, position: 'relative' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <InteractiveContent
                blocks={contentBlocks}
                primaryColor={primaryColor}
                textColor={bubbleTextColor}
                isActionable={!isUser && isLastMessage && !isAgentTyping}
                onQuickAction={onQuickAction}
                onScheduleConfirm={onScheduleConfirm}
              />
            </div>
          </div>
        </div>
      )}

      {/* Feedback row below agent message */}
      {showThumbsArea && (
        <div style={feedbackRowStyle}>
          {feedbackValue ? (
            <div style={singleIconStyle}>
              {feedbackValue === 'good' ? (
                <ThumbsUp size={18} />
              ) : (
                <ThumbsDown size={18} />
              )}
            </div>
          ) : (
            <>
              <button
                type="button"
                style={iconButtonStyle}
                title={t('feedback.thumbsUp')}
                onClick={() => {
                  // Use message_id from socket, fallback to id if message_id doesn't exist
                  const msgId = message.message_id || (message as any).id;
                  if (msgId && onFeedback) {
                    onFeedback(msgId, 'good');
                  } else {
                    // ignore
                  }
                }}
              >
                <ThumbsUp size={18} />
              </button>
              <div style={separatorStyle} />
              <button
                type="button"
                style={iconButtonStyle}
                title={t('feedback.thumbsDown')}
                onClick={() => {
                  // Use message_id from socket, fallback to id if message_id doesn't exist
                  const msgId = message.message_id || (message as any).id;
                  if (msgId && onFeedback) {
                    onFeedback(msgId, 'bad');
                  } else {
                    // ignore
                  }
                }}
              >
                <ThumbsDown size={18} />
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
};
