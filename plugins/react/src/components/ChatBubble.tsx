import React from 'react';
import { Sparkles, X } from 'lucide-react';

interface ChatBubbleProps {
  showChat: boolean;
  onClick: () => void;
  primaryColor: string;
  style?: React.CSSProperties;
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({
  showChat,
  onClick,
  primaryColor,
  style,
}) => {
  const defaultStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    width: '60px',
    height: '60px',
    borderRadius: '50%',
    backgroundColor: primaryColor,
    color: '#ffffff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    zIndex: 1000,
  };

  const chatBubbleStyle: React.CSSProperties = {
    ...defaultStyle,
    ...style,
  };

  return (
    <div style={chatBubbleStyle} onClick={onClick}>
      {showChat ? <X size={24} /> : <Sparkles size={24} />}
    </div>
  );
};
