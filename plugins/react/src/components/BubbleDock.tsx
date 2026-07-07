import React, { useRef, useState } from 'react';
import { ArrowUp, X } from 'lucide-react';
import { ChatBubble } from './ChatBubble';

interface BubbleDockProps {
  primaryColor: string;
  position: string;
  offsetX: number;
  offsetY: number;
  windowWidth: number;
  placeholder: string;
  fontFamily: string;
  fontSize: string;
  chatBubbleIcon?: 'message' | 'sparkles' | 'x';
  /** When false, only the launcher bubble is rendered (quick input hidden/dismissed). */
  showQuickInput: boolean;
  onOpen: () => void;
  onSend: (text: string) => void;
  onDismissQuickInput: () => void;
}

const BUBBLE = 60;
const GAP = 12;
const INPUT_H = 52;
const DEFAULT_W = 240;

export const BubbleDock: React.FC<BubbleDockProps> = ({
  primaryColor,
  position,
  offsetX,
  offsetY,
  windowWidth,
  placeholder,
  fontFamily,
  fontSize,
  chatBubbleIcon,
  showQuickInput,
  onOpen,
  onSend,
  onDismissQuickInput,
}) => {
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const isLeft = position.endsWith('left');
  const isTop = position.startsWith('top');
  const hSide = isLeft ? 'left' : 'right';
  const vSide = isTop ? 'top' : 'bottom';
  // Touch/mobile has no hover, so keep the remove (X) affordance always visible there.
  const isMobile = windowWidth <= 768;

  // Keep everything within the viewport on narrow screens.
  const maxDockW = Math.max(160, windowWidth - offsetX * 2);
  const collapsedW = Math.min(DEFAULT_W, maxDockW - BUBBLE - GAP);
  const coverW = Math.min(collapsedW + BUBBLE + GAP, maxDockW);
  const hasText = value.trim().length > 0;

  const positionStyle = (): React.CSSProperties => ({
    position: 'fixed',
    top: isTop ? offsetY : 'auto',
    bottom: isTop ? 'auto' : offsetY,
    left: isLeft ? offsetX : 'auto',
    right: isLeft ? 'auto' : offsetX,
  });

  const submit = () => {
    const text = value.trim();
    if (!text) return;
    onSend(text);
    setValue('');
    setFocused(false);
    inputRef.current?.blur();
  };

  const bubbleStyle: React.CSSProperties = {
    ...positionStyle(),
    opacity: focused ? 0 : 1,
    transform: focused ? 'scale(0.85)' : 'scale(1)',
    pointerEvents: focused ? 'none' : 'auto',
    transition: 'opacity 200ms ease, transform 200ms ease',
    // `backwards` (not `both`) so the entrance doesn't pin opacity at 1 and block the focus fade-out.
    animation: 'ga-bubble-in 220ms cubic-bezier(0.16, 1, 0.3, 1) backwards',
  };

  // Pill anchors to the bubble's corner; the outer edge stays fixed while it grows over the bubble on focus.
  const pillStyle: React.CSSProperties = {
    position: 'fixed',
    [vSide]: offsetY + (BUBBLE - INPUT_H) / 2,
    [hSide]: focused ? offsetX : offsetX + BUBBLE + GAP,
    width: focused ? coverW : collapsedW,
    height: INPUT_H,
    zIndex: 50,
    display: 'flex',
    alignItems: 'center',
    boxSizing: 'border-box',
    background: '#ffffff',
    border: focused ? '1.5px solid #111111' : '1px solid #e5e7eb',
    borderRadius: 999,
    padding: '0 6px',
    boxShadow: focused ? '0 8px 24px rgba(0, 0, 0, 0.16)' : '0 2px 10px rgba(0, 0, 0, 0.10)',
    transition:
      'right 300ms cubic-bezier(0.16, 1, 0.3, 1), left 300ms cubic-bezier(0.16, 1, 0.3, 1), width 300ms cubic-bezier(0.16, 1, 0.3, 1), border-color 200ms ease, box-shadow 200ms ease',
    animation: 'ga-quickinput-in 320ms cubic-bezier(0.16, 1, 0.3, 1) 200ms both',
  };

  const dismissStyle: React.CSSProperties = {
    position: 'absolute',
    top: -8,
    [isLeft ? 'right' : 'left']: 10,
    width: 22,
    height: 22,
    borderRadius: '50%',
    background: '#111111',
    color: '#ffffff',
    border: '2px solid #ffffff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    padding: 0,
    zIndex: 51,
  };

  const sendStyle: React.CSSProperties = {
    width: 38,
    height: 38,
    borderRadius: '50%',
    flexShrink: 0,
    border: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: hasText ? 'pointer' : 'default',
    background: hasText ? primaryColor : '#eef0f2',
    transition: 'background-color 180ms ease',
    marginLeft: 6,
  };

  return (
    <>
      <ChatBubble
        showChat={false}
        onClick={onOpen}
        primaryColor={primaryColor}
        style={bubbleStyle}
        chatBubbleIcon={chatBubbleIcon}
      />

      {showQuickInput && (
        <div className="ga-quick" style={pillStyle}>
          <button
            type="button"
            className="ga-quick-x"
            style={isMobile ? { ...dismissStyle, opacity: 1, transform: 'scale(1)', pointerEvents: 'auto' } : dismissStyle}
            title="Remove"
            aria-label="Remove quick message"
            onClick={(e) => {
              e.stopPropagation();
              onDismissQuickInput();
            }}
          >
            <X size={12} strokeWidth={3} />
          </button>

          <input
            ref={inputRef}
            type="text"
            value={value}
            placeholder={placeholder}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                submit();
              }
            }}
            style={{
              flex: 1,
              minWidth: 0,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              fontSize,
              fontFamily,
              color: '#111111',
              padding: '0 6px 0 12px',
            }}
          />

          <button
            type="button"
            style={sendStyle}
            title="Send"
            aria-label="Send message"
            disabled={!hasText}
            onMouseDown={(e) => e.preventDefault()}
            onClick={submit}
          >
            <ArrowUp size={18} strokeWidth={3} color={hasText ? '#ffffff' : '#9aa0aa'} />
          </button>
        </div>
      )}
    </>
  );
};
