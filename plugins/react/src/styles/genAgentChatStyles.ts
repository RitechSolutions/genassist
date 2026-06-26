import React from 'react';

export interface ThemeParams {
  primaryColor: string;
  secondaryColor: string;
  backgroundColor: string;
  textColor: string;
  fontFamily: string;
  fontSize: string;
}

export function resolveTheme(theme?: Partial<ThemeParams>): ThemeParams {
  return {
    primaryColor: theme?.primaryColor || '#2962FF',
    backgroundColor: theme?.backgroundColor || '#ffffff',
    textColor: theme?.textColor || '#000000',
    fontFamily: theme?.fontFamily || 'Roboto, Arial, sans-serif',
    fontSize: theme?.fontSize || '14px',
    secondaryColor: theme?.secondaryColor || '#f5f5f5',
  };
}

export function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

interface ContainerStyleParams {
  isFullscreen: boolean;
  isFloatingDocked: boolean;
  windowWidth: number;
  t: ThemeParams;
}

export function getContainerStyle({ isFullscreen, isFloatingDocked, windowWidth, t }: ContainerStyleParams): React.CSSProperties {
  return {
    display: 'flex',
    flexDirection: 'column',
    height: isFullscreen ? undefined : '100%',
    maxHeight: isFullscreen
      ? undefined
      : isFloatingDocked
        ? '100%'
        : windowWidth > 768
          ? '700px'
          : '600px',
    minHeight: isFloatingDocked ? 0 : undefined,
    // When docked, fill the floating wrapper so its (possibly expanded) width drives the size.
    width: isFullscreen ? '100vw' : isFloatingDocked ? '100%' : '380px',
    maxWidth: isFullscreen ? '100vw' : isFloatingDocked ? '100%' : '400px',
    border: isFullscreen ? 'none' : '1px solid #e0e0e0',
    borderRadius: isFullscreen ? '0' : '32px',
    overflow: 'hidden',
    backgroundColor: t.secondaryColor,
    fontFamily: t.fontFamily,
    boxShadow: isFullscreen ? 'none' : "0 4px 20px rgba(0, 0, 0, 0.2)",
    position: isFullscreen ? 'fixed' : 'relative',
    top: isFullscreen ? 0 : undefined,
    left: isFullscreen ? 0 : undefined,
    right: isFullscreen ? 0 : undefined,
    bottom: isFullscreen ? 'env(safe-area-inset-bottom, 0px)' : undefined,
    zIndex: isFullscreen ? 9999 : undefined,
  };
}

export function getHeaderStyle(t: ThemeParams): React.CSSProperties {
  return {
    padding: '12px 14px',
    backgroundColor: t.secondaryColor,
    color: '#111111',
    fontWeight: 'bold',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '8px',
    position: 'relative',
  };
}

// Left/right header zones. Both grow equally (flex: 1) so the centered pill
// stays optically centered regardless of how many buttons sit on each side.
export const headerLeftContainerStyle: React.CSSProperties = {
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-start',
  gap: '4px',
  position: 'relative',
  zIndex: 2,
  minWidth: 0,
};

export const headerRightContainerStyle: React.CSSProperties = {
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: '4px',
  position: 'relative',
  zIndex: 2,
  minWidth: 0,
};

// Floating, centered logo + name pill.
export const headerPillStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  backgroundColor: '#ffffff',
  padding: '6px 16px 6px 8px',
  borderRadius: '999px',
  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.12)',
  maxWidth: '70%',
  flexShrink: 1,
  minWidth: 0,
  position: 'relative',
  // Above the header color-sweep backlight (zIndex 1) so it can't cover the title.
  zIndex: 2,
};

export const logoStyle: React.CSSProperties = {
  width: '26px',
  height: '26px',
  borderRadius: '50%',
  objectFit: 'cover',
  flexShrink: 0,
};

export function getHeaderPillTitleStyle(fontFamily: string): React.CSSProperties {
  return {
    fontSize: '15px',
    fontWeight: 700,
    color: '#111111',
    margin: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    fontFamily,
  };
}

export const headerPillTextColumnStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  minWidth: 0,
};

export function getHeaderDescriptionTextStyle(fontFamily: string): React.CSSProperties {
  return {
    fontSize: '12px',
    fontWeight: 400,
    color: '#6b7280',
    margin: 0,
    paddingTop: '1px',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    fontFamily,
  };
}

export const menuButtonStyle: React.CSSProperties = {
  // No inline backgroundColor here: it would override the `.ga-header-btn:hover` fill.
  color: '#111111',
  border: 'none',
  borderRadius: '50%',
  width: '32px',
  height: '32px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  outline: 'none',
  position: 'relative',
  zIndex: 1,
};

export function getMenuPopupStyle(backgroundColor: string): React.CSSProperties {
  return {
    position: 'absolute',
    top: '50px',
    right: '15px',
    backgroundColor,
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    zIndex: 1000,
    minWidth: '150px',
    overflow: 'visible',
  };
}

export function getMenuItemStyle(t: ThemeParams): React.CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 15px',
    color: t.textColor,
    cursor: 'pointer',
    fontSize: t.fontSize,
    fontFamily: t.fontFamily,
    borderBottom: '1px solid #f0f0f0',
  };
}

export const chatContainerStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  overflowY: 'auto',
  padding: '15px',
  backgroundColor: 'transparent',
  display: 'flex',
  flexDirection: 'column',
};

export const inputContainerStyle: React.CSSProperties = {
  display: 'flex',
  padding: '12px 15px',
  backgroundColor: '#ffffff',
  alignItems: 'center',
  gap: '8px',
  flexShrink: 0,
  overflowX: 'hidden',
  minWidth: 0,
};

export const inputWrapperStyle: React.CSSProperties = {
  display: 'flex',
  flex: 1,
  alignItems: 'center',
  backgroundColor: '#ffffff',
  borderRadius: '24px',
  border: '1px solid #e5e7eb',
  padding: '0 12px',
  minHeight: '50px',
  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.06)',
  position: 'relative',
  overflowX: 'hidden',
  minWidth: 0,
};

interface TextAreaStyleParams {
  textAreaFontSize: string;
  fontFamily: string;
  textAreaLineHeight: number;
  textAreaMaxHeightCalculated: number;
  textColor: string;
}

export function getTextAreaStyle(p: TextAreaStyleParams): React.CSSProperties {
  return {
    flex: 1,
    border: 'none',
    outline: 'none',
    background: 'transparent',
    fontSize: p.textAreaFontSize,
    fontFamily: p.fontFamily,
    padding: '10px',
    paddingRight: '46px',
    color: p.textColor,
    resize: 'none',
    lineHeight: `${p.textAreaLineHeight}px`,
    maxHeight: `${p.textAreaMaxHeightCalculated}px`,
    overflowY: 'hidden',
    overflowX: 'hidden',
    minWidth: 0,
    width: '100%',
    boxSizing: 'border-box',
  };
}

/** Placeholder hint shown in the voice-only footer ("Tap to start a voice conversation"). */
export function getLiveVoiceHintStyle(fontSize: string, fontFamily: string): React.CSSProperties {
  return {
    flex: 1,
    color: '#9ca3af',
    fontSize,
    fontFamily,
    paddingRight: 44,
    userSelect: 'none',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  };
}

export const attachButtonStyle: React.CSSProperties = {
  backgroundColor: 'transparent',
  border: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  outline: 'none',
  color: '#757575',
  padding: 0,
};

export function getSendButtonStyle(primaryColor: string): React.CSSProperties {
  return {
    backgroundColor: primaryColor,
    color: '#ffffff',
    border: 'none',
    borderRadius: '50%',
    width: '36px',
    height: '36px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    outline: 'none',
    flexShrink: 0,
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
  };
}

export const sendButtonDisabledStyle: React.CSSProperties = {
  backgroundColor: '#d1d5db',
  cursor: 'not-allowed',
  opacity: 0.8,
};

export const rightActionContainerStyle: React.CSSProperties = {
  position: 'absolute',
  right: '4px',
  top: '50%',
  transform: 'translateY(-50%)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
};

export function getPossibleQueriesContainerStyle(fontFamily: string): React.CSSProperties {
  return {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '0',
    paddingLeft: '28px',
    paddingRight: '28px',
    marginTop: '5px',
    marginBottom: '15px',
    width: '100%',
    fontFamily,
  };
}

export function getQueryButtonStyle(t: ThemeParams): React.CSSProperties {
  return {
    padding: '12px 15px',
    backgroundColor: t.secondaryColor,
    color: t.textColor,
    border: 'none',
    borderRadius: '6px',
    fontSize: t.fontSize,
    cursor: 'pointer',
    textAlign: 'left',
    fontWeight: 'normal',
    boxShadow: 'none',
    width: '100%',
    maxWidth: '240px',
    fontFamily: t.fontFamily,
  };
}

export function getConfirmOverlayStyle(showResetConfirm: boolean): React.CSSProperties {
  return {
    display: showResetConfirm ? 'flex' : 'none',
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    zIndex: 10,
    justifyContent: 'center',
    alignItems: 'center',
  };
}

export function getConfirmDialogStyle(t: ThemeParams): React.CSSProperties {
  return {
    backgroundColor: t.backgroundColor,
    padding: '20px',
    borderRadius: '8px',
    maxWidth: '300px',
    textAlign: 'center',
    fontFamily: t.fontFamily,
    color: t.textColor,
  };
}

export const confirmButtonsStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'center',
  marginTop: '15px',
  gap: '10px',
};

export function getConfirmButtonStyle(isConfirm: boolean, t: ThemeParams): React.CSSProperties {
  return {
    padding: '8px 16px',
    backgroundColor: isConfirm ? '#F44336' : '#e0e0e0',
    color: isConfirm ? '#ffffff' : t.textColor,
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontFamily: t.fontFamily,
    fontSize: t.fontSize,
  };
}

export function getContentCardStyle(backgroundColor: string): React.CSSProperties {
  return {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    boxShadow: '0 -2px 6px rgba(0,0,0,0.03)',
    position: 'relative',
    zIndex: 2,
    overflow: 'hidden',
    minHeight: 0,
  };
}

export function getDisclaimerStyle(fontFamily: string): React.CSSProperties {
  return {
    textAlign: 'left',
    fontSize: '12px',
    color: '#9ca3af',
    margin: '12px 4px 2px 4px',
    fontFamily,
  };
}

interface PositionParams {
  position: string;
  offsetX: number;
  offsetY: number;
}

export function getPositionStyles({ position, offsetX, offsetY }: PositionParams): React.CSSProperties {
  const base: React.CSSProperties = {
    position: 'fixed',
    zIndex: 1000,
  };

  switch (position) {
    case 'bottom-right':
      return { ...base, bottom: offsetY, right: offsetX };
    case 'bottom-left':
      return { ...base, bottom: offsetY, left: offsetX };
    case 'top-right':
      return { ...base, top: offsetY, right: offsetX };
    case 'top-left':
      return { ...base, top: offsetY, left: offsetX };
    default:
      return { ...base, bottom: offsetY, right: offsetX };
  }
}

export function getChatPositionStyles({ position, offsetX, offsetY }: PositionParams): React.CSSProperties {
  const base: React.CSSProperties = {
    position: 'fixed',
    borderRadius: '32px',
    zIndex: 1004,
  };

  switch (position) {
    case 'bottom-right':
      return { ...base, bottom: offsetY, right: offsetX };
    case 'bottom-left':
      return { ...base, bottom: offsetY, left: offsetX };
    case 'top-right':
      return { ...base, top: offsetY, right: offsetX };
    case 'top-left':
      return { ...base, top: offsetY, left: offsetX };
    default:
      return { ...base, bottom: offsetY, right: offsetX };
  }
}

interface ResponsiveDimensionParams {
  isFullscreen: boolean;
  mode: string;
  isExpanded?: boolean;
}

export function getResponsiveDimensions({ isFullscreen, mode, isExpanded = false }: ResponsiveDimensionParams): React.CSSProperties {
  const screenWidth = typeof window !== 'undefined' ? window.innerWidth : 1024;
  const fallbackHeight = isFullscreen ? '100vh' : '60vh';

  if (isFullscreen) {
    return { width: '100vw', height: fallbackHeight, borderRadius: '0' };
  }

  if (mode === 'floating') {
    if (screenWidth <= 480) {
      return { width: 'calc(100vw - 40px)' };
    }
    if (screenWidth <= 768) {
      return { width: '350px' };
    }
    return { width: isExpanded ? '540px' : '380px' };
  }

  if (screenWidth <= 480) {
    return { width: 'calc(100vw - 40px)', height: fallbackHeight };
  }
  if (screenWidth <= 768) {
    return { width: '350px', height: fallbackHeight };
  }

  return { width: '380px', height: fallbackHeight };
}

interface FloatingShellParams {
  windowHeight: number;
  offsetY: number;
  position: string;
  isExpanded?: boolean;
}

export function getFloatingShellStyle({ windowHeight, offsetY, position, isExpanded = false }: FloatingShellParams): React.CSSProperties {
  const screenWidth = typeof window !== 'undefined' ? window.innerWidth : 1024;
  const screenHeight = typeof window !== 'undefined' ? window.innerHeight : 1080;
  const margin = 10;
  // Expansion is width-focused; expanded uses most of the available height.
  const usableHeight = Math.max(280, windowHeight - offsetY - margin * (isExpanded ? 2 : 10));
  let maxHeight: number | string = usableHeight;

  if (screenWidth >= 765 && screenHeight >= 1070) {
    maxHeight = isExpanded ? '86vh' : '60vh';
  }

  return {
    display: 'flex',
    flexDirection: 'column',
    maxHeight: maxHeight,
    height: usableHeight,
    ...(position === 'top-right' || position === 'top-left'
      ? { top: offsetY, bottom: 'auto' }
      : { top: 'auto', bottom: offsetY }),
  };
}

interface FloatingContainerParams {
  mode: string;
  isFullscreen: boolean;
  windowWidth: number;
  windowHeight: number;
  position: string;
  offsetX: number;
  offsetY: number;
  isExpanded?: boolean;
}

// Anchor the open/close scale animation to the corner nearest the launcher bubble.
function getTransformOrigin(position: string): string {
  switch (position) {
    case 'bottom-left': return 'bottom left';
    case 'top-right': return 'top right';
    case 'top-left': return 'top left';
    case 'bottom-right':
    default: return 'bottom right';
  }
}

export function getFloatingContainerStyle(p: FloatingContainerParams): React.CSSProperties {
  return {
    transformOrigin: getTransformOrigin(p.position),
    ...((p.mode === 'fullscreen' || p.isFullscreen)
      ? {
          position: 'fixed' as const,
          top: 0,
          left: 0,
          right: 0,
          bottom: 'env(safe-area-inset-bottom, 0px)',
          borderRadius: '0',
          zIndex: 9999,
        }
      : {
          ...getChatPositionStyles({ position: p.position, offsetX: p.offsetX, offsetY: p.offsetY }),
          ...getResponsiveDimensions({ isFullscreen: p.isFullscreen, mode: p.mode, isExpanded: p.isExpanded }),
          ...(p.mode === 'floating' && !p.isFullscreen ? getFloatingShellStyle({ windowHeight: p.windowHeight, offsetY: p.offsetY, position: p.position, isExpanded: p.isExpanded }) : {}),
          // Smooth, simple ease for the maximize/minimize (expand/collapse) resize.
          transition: 'width 280ms cubic-bezier(0.16, 1, 0.3, 1), height 280ms cubic-bezier(0.16, 1, 0.3, 1), max-height 280ms cubic-bezier(0.16, 1, 0.3, 1)',
        }
    ),
  };
}

export const CSS_KEYFRAMES = `
  @keyframes blink { 0% { opacity: 0.2; } 20% { opacity: 1; } 100% { opacity: 0.2; } }
  .ga-textarea-nosb {
    scrollbar-width: none;
    -ms-overflow-style: none;
    max-width: 100%;
    box-sizing: border-box;
  }
  .ga-textarea-nosb::-webkit-scrollbar { width: 0; height: 0; }
  .ga-input-disclaimer a {
    color: #9ca3af !important;
    text-decoration: underline;
  }
  .ga-input-disclaimer a:hover {
    color: #6b7280 !important;
  }
  @media (max-width: 768px) {
    .ga-textarea-nosb {
      font-size: 16px !important;
    }
  }
  @keyframes ga-backlight-sweep2 { 0% { transform: translateX(-35%); } 100% { transform: translateX(105%); } }
  @keyframes ga-backlight-pulse { 0%,100% { opacity: 0.7; } 50% { opacity: 1; } }
  @keyframes ga-think-change { 0% { opacity: 0; transform: translateY(4px); } 100% { opacity: 1; transform: translateY(0); } }
  @keyframes ga-widget-in {
    from { opacity: 0; transform: translateY(16px) scale(0.96); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes ga-widget-out {
    from { opacity: 1; transform: translateY(0) scale(1); }
    to   { opacity: 0; transform: translateY(16px) scale(0.96); }
  }
  /* fill backwards (not both): keep the entrance-from state, but drop the transform at rest so it
     does not become a containing block for the inner fixed-position fullscreen panel. */
  .ga-widget-in  { animation: ga-widget-in 260ms cubic-bezier(0.16, 1, 0.3, 1) backwards; }
  .ga-widget-out { animation: ga-widget-out 200ms cubic-bezier(0.4, 0, 1, 1) both; }
  @keyframes ga-bubble-in {
    from { opacity: 0; transform: scale(0.8); }
    to   { opacity: 1; transform: scale(1); }
  }
  @keyframes ga-quickinput-in {
    from { opacity: 0; transform: scale(0.94); }
    to   { opacity: 1; transform: scale(1); }
  }
  .ga-quick .ga-quick-x {
    opacity: 0;
    transform: scale(0.8);
    pointer-events: none;
    transition: opacity 160ms ease, transform 160ms ease;
  }
  .ga-quick:hover .ga-quick-x {
    opacity: 1;
    transform: scale(1);
    pointer-events: auto;
  }
  .ga-header-btn { background-color: transparent; transition: background-color 0.15s ease; }
  .ga-header-btn:hover { background-color: rgba(0, 0, 0, 0.06); }
  @media (prefers-reduced-motion: reduce) {
    .ga-widget-in, .ga-widget-out { animation: none !important; }
    .ga-quick { animation: none !important; }
  }
  .grecaptcha-badge {
    display: none !important;
    visibility: hidden !important;
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
  }
`;
