import React from 'react';
import { MessageCircle, Sparkles, X } from 'lucide-react';

interface ChatBubbleProps {
  showChat: boolean;
  onClick: () => void;
  primaryColor: string;
  style?: React.CSSProperties;
  chatBubbleIcon?: 'message' | 'sparkles' | 'x';
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({
  showChat,
  onClick,
  primaryColor,
  style,
  chatBubbleIcon,
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
    zIndex: 40,
  };

  const chatBubbleStyle: React.CSSProperties = {
    ...defaultStyle,
    ...style,
  };

  console.log('chatBubbleIcon', chatBubbleIcon);

  return (
    <div style={chatBubbleStyle} onClick={onClick}>
      {showChat ? <X size={24} /> : chatBubbleIcon === 'message' ? <MessageCircle size={30} /> : chatBubbleIcon === 'sparkles' ? <Sparkles size={24} /> : <X size={24} />}
    </div>
  );
};
