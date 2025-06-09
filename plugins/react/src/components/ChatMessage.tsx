import React from 'react';
import { ChatMessage } from '../types';
import { User } from 'lucide-react';

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
}

export const ChatMessageComponent: React.FC<ChatMessageProps> = ({
  message,
  theme,
  onPlayAudio,
  isPlayingAudio,
  isFirstMessage = false,
  isNextSameSpeaker = false,
  isPrevSameSpeaker = false
}) => {
  const isUser = message.speaker === 'customer';
  const isSpecial = message.speaker === 'special';
  const isWelcomeMessage = !isUser && !isSpecial && isFirstMessage;

  const formatTimestamp = (timestamp: number) => {
    try {
      if (!timestamp || isNaN(timestamp)) {
        return 'Just now';
      }
      
      const timestampMs = timestamp < 1000000000000 ? timestamp * 1000 : timestamp;
      
      const date = new Date(timestampMs);
      // Quick check if date is valid
      if (isNaN(date.getTime())) {
        return 'Just now';
      }
      
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      
      // Format time as HH:MM AM/PM
      const timeOptions: Intl.DateTimeFormatOptions = { hour: 'numeric', minute: '2-digit', hour12: true };
      const timeStr = date.toLocaleTimeString(undefined, timeOptions);
      
      // Check if date is today, yesterday, or another day
      if (date.toDateString() === today.toDateString()) {
        return `Today, ${timeStr}`;
      } else if (date.toDateString() === yesterday.toDateString()) {
        return `Yesterday, ${timeStr}`;
      } else {
        // Format date as Month DD, YYYY
        const dateOptions: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' };
        const dateStr = date.toLocaleDateString(undefined, dateOptions);
        return `${dateStr}, ${timeStr}`;
      }
    } catch (error) {
      console.error('Error formatting timestamp:', error);
      return 'Just now';
    }
  };

  const timestamp = formatTimestamp(message.create_time);

  const userBubbleBgColor = theme?.primaryColor || '#2563EB';
  const userTextColor = '#ffffff';
  const agentBubbleBgColor = theme?.secondaryColor || '#eeeeee';
  const agentTextColor = '#000000';
  const fontFamily = theme?.fontFamily || 'Roboto, Arial, sans-serif';
  const fontSize = theme?.fontSize || '15px';

  const messageContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    marginBottom: isPrevSameSpeaker ? '8px' : '8px',
    marginTop: isPrevSameSpeaker ? '0px' : '16px',
    position: 'relative',
    alignItems: isUser ? 'flex-end' : 'flex-start',
  };

  const messageRowStyle: React.CSSProperties = {
    display: 'flex',
    width: '100%',
    justifyContent: isUser ? 'flex-end' : 'flex-start',
  };

  const labelContainerStyle: React.CSSProperties = {
    display: isPrevSameSpeaker ? 'none' : 'flex',
    width: '80%',
    justifyContent: isUser ? 'flex-end' : 'flex-start',
    marginBottom: '4px',
  };

  const messageLabelStyle: React.CSSProperties = {
    fontSize: '12px',
    color: '#757575',
    lineHeight: 1,
  };

  const messageBubbleContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    maxWidth: '80%',
  };

  const bubbleStyle: React.CSSProperties = {
    backgroundColor: isUser 
      ? userBubbleBgColor
      : agentBubbleBgColor,
    color: isUser ? userTextColor : agentTextColor,
    padding: '12px 16px',
    borderRadius: '8px',
    fontSize,
    fontFamily,
    wordBreak: 'break-word',
    lineHeight: 1.4,
    maxWidth: '100%',
  };

  const timestampStyle: React.CSSProperties = {
    fontSize: '11px',
    color: '#757575',
    marginTop: '4px',
    width: '80%',
    textAlign: isUser ? 'right' : 'left',
    display: isNextSameSpeaker ? 'none' : 'block', // Hide timestamp if next message is from same speaker
  };

  const welcomeTitleStyle: React.CSSProperties = {
    fontSize: '18px',
    fontWeight: 'bold',
    marginBottom: '4px',
    color: '#000000',
  };

  const welcomeContentStyle: React.CSSProperties = {
    fontSize: '16px',
    fontWeight: 'normal',
    color: '#000000',
  };

  const speakerLabel = isUser ? 'You' : isSpecial ? 'System' : 'Agent';

  let welcomeTitle = '';
  let welcomeContent = '';
  
  if (isWelcomeMessage) {
    const messageText = message.text;
    if (messageText.toLowerCase().startsWith('')) {
      const parts = messageText.split(/[,.!?]/);
      if (parts.length > 0) {
        welcomeTitle = parts[0].trim();
        welcomeContent = messageText.substring(welcomeTitle.length).trim();
        // Remove any punctuation at the start
        welcomeContent = welcomeContent.replace(/^[,.!?\s]+/, '');
      }
    } else {
      welcomeTitle = '';
      welcomeContent = messageText;
    }
  }

  const messageLines = !isWelcomeMessage ? message.text.split('\n').map((line, i) => (
    <React.Fragment key={i}>
      {line}
      {i < message.text.split('\n').length - 1 && <br />}
    </React.Fragment>
  )) : null;

  // Handle special messages (like takeover indicators)
  if (isSpecial) {
    const specialMessageStyle: React.CSSProperties = {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      margin: '16px 0',
      width: '100%',
    };

    const specialBubbleStyle: React.CSSProperties = {
      backgroundColor: '#E3F2FD',
      color: '#1976D2',
      padding: '8px 16px',
      borderRadius: '16px',
      fontSize: '14px',
      fontFamily,
      fontWeight: '500',
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
    };

    return (
      <div style={specialMessageStyle}>
        <div style={specialBubbleStyle}>
          <User size={15} />
          {message.text}
        </div>
      </div>
    );
  }

  if (isWelcomeMessage) {
    return (
      <div style={messageContainerStyle}>
        <div style={messageBubbleContainerStyle}>
          <div style={labelContainerStyle}>
            <div style={messageLabelStyle}>Agent</div>
          </div>
          <div style={messageRowStyle}>
            <div style={{...bubbleStyle, backgroundColor: theme?.primaryColor || '#2563EB', color: '#ffffff'}}>
              {message.text}
            </div>
          </div>
          <div style={timestampStyle}>{timestamp}</div>
        </div>
      </div>
    );
  }

  return (
    <div style={messageContainerStyle}>
      <div style={labelContainerStyle}>
        <div style={messageLabelStyle}>{speakerLabel}</div>
      </div>
      <div style={bubbleStyle}>
        {messageLines}
      </div>
      <div style={timestampStyle}>{timestamp}</div>
    </div>
  );
}; 