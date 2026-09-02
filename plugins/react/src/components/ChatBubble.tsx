import React from 'react';
import { MessageCircle, Sparkles, X } from 'lucide-react';

interface ChatBubbleProps {
  showChat: boolean;
  onClick: () => void;
  primaryColor: string;
  style?: React.CSSProperties;
  chatBubbleIcon?: 'message' | 'sparkles' | 'x';
  /** Count of unseen agent/supervisor messages; shows a badge when > 0 and closed. */
  unreadCount?: number;
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({
  showChat,
  onClick,
  primaryColor,
  style,
  chatBubbleIcon,
  unreadCount = 0,
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

  const showBadge = !showChat && unreadCount > 0;

  const badgeStyle: React.CSSProperties = {
    position: 'absolute',
    top: '-2px',
    right: '-2px',
    minWidth: '20px',
    height: '20px',
    padding: '0 6px',
    boxSizing: 'border-box',
    borderRadius: '10px',
    backgroundColor: '#ef4444',
    color: '#ffffff',
    fontSize: '12px',
    fontWeight: 700,
    lineHeight: '20px',
    textAlign: 'center',
    boxShadow: '0 0 0 2px #ffffff',
    pointerEvents: 'none',
  };

  return (
    <div style={chatBubbleStyle} onClick={onClick}>
      {showChat ? <X size={24} /> : chatBubbleIcon === 'message' ? <MessageCircle size={30} /> : chatBubbleIcon === 'x' ? <X size={24} /> : <Sparkles size={24} />}
      {showBadge && (
        <span style={badgeStyle} aria-label={`${unreadCount} unread`}>
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </div>
  );
};
