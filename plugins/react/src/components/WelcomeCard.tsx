import React from 'react';
import { parseBoldText } from './InteractiveContent';

interface ThemeLike {
  primaryColor?: string;
  secondaryColor?: string;
  fontFamily?: string;
  fontSize?: string;
  backgroundColor?: string;
  textColor?: string;
}

export interface WelcomeCardProps {
  theme?: ThemeLike;
  imageUrl?: string;
  title?: string;
  content?: string;
  possibleQueries?: string[];
  onQuickQuery?: (query: string) => void;
  isAgentTyping?: boolean;
}

export const WelcomeCard: React.FC<WelcomeCardProps> = ({
  theme,
  imageUrl,
  title,
  content,
  possibleQueries,
  onQuickQuery,
  isAgentTyping = false,
}) => {
  const agentTextColor = '#000000';
  const fontFamily = theme?.fontFamily || 'Roboto, Arial, sans-serif';

  const isClickable = onQuickQuery && !isAgentTyping;
  const chipStyle: React.CSSProperties = {
    display: 'inline-block',
    backgroundColor: theme?.primaryColor || '#5B3DF5',
    color: '#fff',
    padding: '8px 12px',
    borderRadius: 12,
    fontSize: '14px',
    marginRight: 8,
    marginBottom: 8,
    cursor: isClickable ? 'pointer' : 'default',
    userSelect: 'none',
    opacity: isAgentTyping ? 0.6 : 1,
  };

  const chipContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    marginTop: 8,
  };

  const welcomeTitleStyle: React.CSSProperties = {
    fontSize: '22px',
    fontWeight: 700,
    margin: '8px 0 4px 0',
    color: agentTextColor,
    fontFamily,
  };

  const welcomeSubtitleStyle: React.CSSProperties = {
    fontSize: '14px',
    color: '#6b7280',
    margin: 0,
    fontFamily,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-start', textAlign: 'left' }}>
      {imageUrl && (
        <div style={{ display: 'flex', gap: 16 }}>
          <img
            src={imageUrl}
            style={{ width: 160, height: 160, objectFit: 'contain', borderRadius: 12, display: 'block' }}
          />
        </div>
      )}
      {title && <div style={welcomeTitleStyle}>{title}</div>}
      {content && <div style={welcomeSubtitleStyle}>{parseBoldText(content)}</div>}
      {possibleQueries && possibleQueries.length > 0 && (
        <div style={chipContainerStyle}>
          {possibleQueries.map((q, idx) => (
            <span 
              key={idx} 
              style={chipStyle} 
              onClick={() => {
                if (isAgentTyping) return;
                onQuickQuery && onQuickQuery(q);
              }}
            >
              {q}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

