import React from 'react';
import { ChatMessage } from '../types';

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
}

export const ChatMessageComponent: React.FC<ChatMessageProps> = ({
  message,
  theme,
  onPlayAudio,
  isPlayingAudio
}) => {
  const isUser = message.speaker === 'customer';

  const messageStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: isUser ? 'flex-end' : 'flex-start',
    marginBottom: '10px',
    maxWidth: '80%',
  };

  const bubbleStyle: React.CSSProperties = {
    backgroundColor: isUser 
      ? theme?.primaryColor || '#007bff'
      : theme?.secondaryColor || '#f0f0f0',
    color: isUser ? '#ffffff' : theme?.textColor || '#333333',
    padding: '10px 15px',
    borderRadius: '15px',
    fontSize: theme?.fontSize || '14px',
    fontFamily: theme?.fontFamily || 'Arial, sans-serif',
    wordBreak: 'break-word',
  };

  const timestampStyle: React.CSSProperties = {
    fontSize: '12px',
    color: '#666',
    marginTop: '5px',
    fontFamily: theme?.fontFamily || 'Arial, sans-serif',
  };

  const audioButtonStyle: React.CSSProperties = {
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    padding: '5px',
    marginLeft: '10px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    opacity: isPlayingAudio ? 0.5 : 1,
    pointerEvents: isPlayingAudio ? 'none' : 'auto',
  };

  return (
    <div style={messageStyle}>
      <div style={bubbleStyle}>
        {message.text}
        {!isUser && onPlayAudio && (
          <button
            style={audioButtonStyle}
            onClick={() => onPlayAudio(message.text)}
            title="Play audio"
            disabled={isPlayingAudio}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M5 3l14 9-14 9V3z" />
            </svg>
          </button>
        )}
      </div>
      <div style={timestampStyle}>
        {new Date(message.create_time).toLocaleTimeString()}
      </div>
    </div>
  );
}; 