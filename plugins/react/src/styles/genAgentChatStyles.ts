import React from 'react';

export interface ThemeParams {
  primaryColor: string;
  secondaryColor: string;
  backgroundColor: string;
  textColor: string;
  fontFamily: string;
  fontSize: string;
  /** Background of the visitor's (customer) message bubble. */
  userBubbleColor: string;
  /** Background of the input field / docked bar / voice overlay. */
  inputBackgroundColor: string;
  /** Border color used across the container, inputs, menus and dialogs. */
  borderColor: string;
  /** Secondary/muted text: timestamps, descriptions, disclaimers, placeholders. */
  mutedTextColor: string;
}

export function resolveTheme(theme?: Partial<ThemeParams>): ThemeParams {
  return {
    primaryColor: theme?.primaryColor || '#2962FF',
    backgroundColor: theme?.backgroundColor || '#ffffff',
    textColor: theme?.textColor || '#000000',
    fontFamily: theme?.fontFamily || 'Roboto, Arial, sans-serif',
    fontSize: theme?.fontSize || '14px',
    secondaryColor: theme?.secondaryColor || '#f5f5f5',
    userBubbleColor: theme?.userBubbleColor || '#E4E4E7',
    inputBackgroundColor: theme?.inputBackgroundColor || '#ffffff',
    borderColor: theme?.borderColor || '#e5e7eb',
    mutedTextColor: theme?.mutedTextColor || '#6b7280',
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
    border: isFullscreen ? 'none' : `1px solid ${t.borderColor}`,
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
    color: t.textColor,
    fontWeight: 'bold',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '8px',
    position: 'relative',
  };
}

// Left header zone grows to fill (flex: 1) and holds the logo/name group +
// hover-revealed expand button; the right zone shrinks to its buttons.
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
  flex: '0 0 auto',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: '4px',
  position: 'relative',
  zIndex: 2,
};

// Left-aligned logo + name group. Slides right on header hover (see .ga-header CSS).
export const headerPillStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: 0,
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

// Full brand logo/wordmark shown instead of the small logo + title + description.
// Fixed height fills the header; width stays auto and clamps to the group's maxWidth.
export const brandLogoStyle: React.CSSProperties = {
  height: '30px',
  width: 'auto',
  maxWidth: '100%',
  objectFit: 'contain',
  display: 'block',
  flexShrink: 1,
  minWidth: 0,
};

export function getHeaderPillTitleStyle(fontFamily: string, textColor: string = '#111111'): React.CSSProperties {
  return {
    fontSize: '15px',
    fontWeight: 700,
    color: textColor,
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

export function getHeaderDescriptionTextStyle(fontFamily: string, mutedTextColor: string = '#6b7280'): React.CSSProperties {
  return {
    fontSize: '12px',
    fontWeight: 400,
    color: mutedTextColor,
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

// Popover styling mirrors the web app's shadcn dropdown-menu: rounded-md (10px),
// 1px border, shadow-md, p-1 (4px) padding around rounded, hover-highlighted items.
export function getMenuPopupStyle(backgroundColor: string, borderColor: string = '#e4e4e7'): React.CSSProperties {
  return {
    position: 'absolute',
    top: '50px',
    right: '15px',
    backgroundColor,
    borderRadius: '10px',
    border: `1px solid ${borderColor}`,
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
    padding: '4px',
    zIndex: 1000,
    minWidth: '160px',
    overflow: 'visible',
  };
}

// Menu item mirrors shadcn DropdownMenuItem: rounded-sm (8px), px-2 py-1.5, text-sm,
// hover:bg-accent. Hover fill comes from the --ga-hover CSS var (see .ga-menu-item).
export function getMenuItemStyle(t: ThemeParams): React.CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '6px 8px',
    borderRadius: '8px',
    color: t.textColor,
    cursor: 'pointer',
    fontSize: t.fontSize,
    fontFamily: t.fontFamily,
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

export function getInputContainerStyle(inputBackgroundColor: string = '#ffffff'): React.CSSProperties {
  return {
    display: 'flex',
    padding: '12px 15px',
    backgroundColor: inputBackgroundColor,
    alignItems: 'center',
    gap: '8px',
    flexShrink: 0,
    overflowX: 'hidden',
    minWidth: 0,
  };
}

export function getInputWrapperStyle(inputBackgroundColor: string = '#ffffff', borderColor: string = '#e5e7eb'): React.CSSProperties {
  return {
    display: 'flex',
    flex: 1,
    alignItems: 'center',
    backgroundColor: inputBackgroundColor,
    borderRadius: '24px',
    border: `1px solid ${borderColor}`,
    padding: '0 12px',
    minHeight: '50px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.06)',
    position: 'relative',
    overflowX: 'hidden',
    minWidth: 0,
  };
}

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
export function getLiveVoiceHintStyle(fontSize: string, fontFamily: string, mutedTextColor: string = '#9ca3af'): React.CSSProperties {
  return {
    flex: 1,
    color: mutedTextColor,
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
    // Matches the web app's AlertDialog overlay (bg-black/80).
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    zIndex: 10,
    justifyContent: 'center',
    alignItems: 'center',
    padding: '16px',
  };
}

// Dialog mirrors shadcn AlertDialogContent: rounded-lg (12px), p-6 (24px),
// 1px border, shadow-lg, left-aligned text.
export function getConfirmDialogStyle(t: ThemeParams): React.CSSProperties {
  return {
    backgroundColor: t.backgroundColor,
    padding: '24px',
    borderRadius: '12px',
    border: `1px solid ${t.borderColor}`,
    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
    maxWidth: '320px',
    width: '100%',
    textAlign: 'left',
    fontFamily: t.fontFamily,
    color: t.textColor,
  };
}

export const confirmButtonsStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'flex-end',
  marginTop: '20px',
  gap: '8px',
};

// Buttons mirror shadcn Button: pill (rounded-full), text-sm font-medium.
// Confirm = destructive (red-600), Cancel = outline. Hover via .ga-confirm-btn CSS.
export function getConfirmButtonStyle(isConfirm: boolean, t: ThemeParams): React.CSSProperties {
  return {
    padding: '8px 16px',
    backgroundColor: isConfirm ? '#dc2626' : 'transparent',
    color: isConfirm ? '#ffffff' : t.textColor,
    border: isConfirm ? 'none' : `1px solid ${t.borderColor}`,
    borderRadius: '9999px',
    cursor: 'pointer',
    fontFamily: t.fontFamily,
    fontSize: t.fontSize,
    fontWeight: 500,
    transition: 'background-color 0.15s ease',
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

export function getDisclaimerStyle(fontFamily: string, mutedTextColor: string = '#9ca3af'): React.CSSProperties {
  return {
    textAlign: 'left',
    fontSize: '12px',
    color: mutedTextColor,
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

/* ===== Input-bar variant styles ===== */

// Outer wrapper: fixed to the viewport so the bar stays docked and visible on scroll
// (like the floating launcher), regardless of where the host places the component in the
// page. It's still a positioned element, so the FAQ list / conversation panel keep floating
// above the bar. Always docked bottom-center — the input bar ignores floatingConfig corners.
// Margin-auto centering (rather than a transform) keeps the element from becoming a
// containing block for any fixed-position descendants.
export function getInputBarRootStyle(fontFamily: string, offsetY: number = 24): React.CSSProperties {
  return {
    position: 'fixed',
    zIndex: 1000,
    bottom: offsetY,
    left: 0,
    right: 0,
    marginLeft: 'auto',
    marginRight: 'auto',
    width: 'calc(100vw - 40px)',
    maxWidth: '680px',
    boxSizing: 'border-box',
    fontFamily,
  };
}

// The docked "Chat Input" pill itself.
export function getInputBarBarStyle(inputBackgroundColor: string = '#ffffff', borderColor: string = '#e5e7eb'): React.CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    width: '100%',
    boxSizing: 'border-box',
    background: inputBackgroundColor,
    border: `1px solid ${borderColor}`,
    borderRadius: '28px',
    padding: '6px 8px 6px 16px',
    boxShadow: '0 6px 24px rgba(0, 0, 0, 0.10)',
    position: 'relative',
    minWidth: 0,
  };
}

// Floating layer anchored just above the bar (shared by the FAQ list and the panel).
const inputBarFloatingBase: React.CSSProperties = {
  position: 'absolute',
  left: 0,
  right: 0,
  bottom: 'calc(100% + 12px)',
  zIndex: 40,
};

export function getInputBarFaqListStyle(): React.CSSProperties {
  return {
    ...inputBarFloatingBase,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: '8px',
  };
}

export function getInputBarFaqChipStyle(t: ThemeParams): React.CSSProperties {
  return {
    alignSelf: 'flex-start',
    maxWidth: '100%',
    textAlign: 'left',
    padding: '12px 18px',
    borderRadius: '22px',
    border: 'none',
    // Standalone pill using the agent's configured primary color (matches the welcome-card FAQs).
    background: t.primaryColor,
    color: '#ffffff',
    fontSize: t.fontSize,
    fontFamily: t.fontFamily,
    fontWeight: 500,
    lineHeight: 1.3,
    cursor: 'pointer',
    boxShadow: '0 2px 12px rgba(0, 0, 0, 0.14)',
    outline: 'none',
  };
}

// Compact "agent replied" preview shown above the collapsed bar when a response arrives
// while the conversation panel is closed. Width/margin are set by the caller so it tracks
// the bar's collapsed/expanded width.
export function getInputBarReplyCardStyle(backgroundColor: string, borderColor: string = '#ececec'): React.CSSProperties {
  return {
    ...inputBarFloatingBase,
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    textAlign: 'left',
    padding: '12px 16px',
    background: backgroundColor,
    border: `1px solid ${borderColor}`,
    borderRadius: '22px',
    boxShadow: '0 10px 32px rgba(0, 0, 0, 0.12)',
    cursor: 'pointer',
    boxSizing: 'border-box',
    outline: 'none',
  };
}

export function getInputBarPanelStyle(backgroundColor: string, borderColor: string = '#ececec'): React.CSSProperties {
  return {
    ...inputBarFloatingBase,
    transformOrigin: 'bottom center',
    display: 'flex',
    flexDirection: 'column',
    height: 'min(70vh, 520px)',
    maxHeight: 'min(70vh, 520px)',
    background: backgroundColor,
    border: `1px solid ${borderColor}`,
    borderRadius: '20px',
    boxShadow: '0 14px 44px rgba(0, 0, 0, 0.16)',
    overflow: 'hidden',
  };
}

export function getInputBarPanelHeaderStyle(backgroundColor: string): React.CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 12px',
    // No divider — messages fade out under the header via the gradient overlay below it.
    background: backgroundColor,
    flexShrink: 0,
    position: 'relative',
    // Above the message-fade overlay.
    zIndex: 6,
  };
}

// Circular "jump to latest" button, docked bottom-center over the message list. Uses the
// panel background so it stays theme-aware; keep the translateX(-50%) in sync with the
// .ga-scroll-bottom-btn CSS below (hover/entrance transforms must preserve the centering).
export function getScrollToBottomButtonStyle(backgroundColor: string): React.CSSProperties {
  return {
    position: 'absolute',
    bottom: '14px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 20,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '34px',
    height: '34px',
    borderRadius: '50%',
    background: backgroundColor || '#ffffff',
    border: '1px solid #e5e7eb',
    boxShadow: '0 4px 14px rgba(0, 0, 0, 0.16)',
    color: '#374151',
    cursor: 'pointer',
    padding: 0,
  };
}

export const CSS_KEYFRAMES = `
  @keyframes blink { 0% { opacity: 0.2; } 20% { opacity: 1; } 100% { opacity: 0.2; } }
  @keyframes ga-scroll-btn-in { from { opacity: 0; transform: translateX(-50%) translateY(6px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
  .ga-scroll-bottom-btn { animation: ga-scroll-btn-in 180ms ease; transition: transform 160ms ease, box-shadow 160ms ease; }
  .ga-scroll-bottom-btn:hover { transform: translateX(-50%) translateY(-1px); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22); }
  .ga-textarea-nosb {
    scrollbar-width: none;
    -ms-overflow-style: none;
    max-width: 100%;
    box-sizing: border-box;
  }
  .ga-textarea-nosb::-webkit-scrollbar { width: 0; height: 0; }
  /* Custom scrollbar for the message list (all modes). Thin, rounded, subtle; the thumb
     shows on hover/scroll and darkens on hover. Firefox uses scrollbar-width/color. */
  .ga-scroll {
    scrollbar-width: thin;
    scrollbar-color: rgba(100, 116, 139, 0.35) transparent;
  }
  .ga-scroll::-webkit-scrollbar { width: 8px; height: 8px; }
  .ga-scroll::-webkit-scrollbar-track { background: transparent; }
  .ga-scroll::-webkit-scrollbar-thumb {
    background-color: rgba(100, 116, 139, 0.35);
    border-radius: 999px;
    border: 2px solid transparent;
    background-clip: padding-box;
    transition: background-color 0.2s ease;
    min-height: 40px;
  }
  .ga-scroll::-webkit-scrollbar-thumb:hover {
    background-color: rgba(100, 116, 139, 0.6);
    background-clip: padding-box;
  }
  .ga-scroll::-webkit-scrollbar-corner { background: transparent; }
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
  /* Neutral overlay so the hover reads on both light and dark themes. */
  .ga-header-btn:hover { background-color: rgba(127, 127, 127, 0.16); }
  /* Menu popover items: shadcn-style hover highlight (bg-accent). --ga-hover is the
     theme's secondary color, set on the widget root. */
  .ga-menu-item { transition: background-color 0.15s ease; }
  .ga-menu-item:hover { background-color: var(--ga-hover, #f4f4f5); }
  /* Reset dialog buttons: destructive hover (red-700) + outline-cancel hover (bg-accent). */
  .ga-confirm-btn--danger:hover { background-color: #b91c1c; }
  .ga-confirm-btn--cancel:hover { background-color: var(--ga-hover, #f4f4f5); }
  /* Hovering the left logo section reveals the expand button (collapsed to 0 width
     by default), which pushes the logo/name group to the right for a slide-in.
     Scoped to .ga-header-left so hovering the right-side buttons never triggers it. */
  .ga-header-expand-btn {
    width: 0;
    min-width: 0;
    overflow: hidden;
    opacity: 0;
    transform: scale(0.85);
    pointer-events: none;
    transition: width 260ms cubic-bezier(0.16, 1, 0.3, 1), opacity 200ms ease, transform 200ms ease;
  }
  .ga-header-left:hover .ga-header-expand-btn,
  .ga-header-left:focus-within .ga-header-expand-btn {
    width: 32px;
    opacity: 1;
    transform: scale(1);
    pointer-events: auto;
  }
  /* Hovering the left logo section reveals the agent description (collapsed by default). */
  .ga-header-desc {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows 260ms cubic-bezier(0.16, 1, 0.3, 1);
  }
  .ga-header-left:hover .ga-header-desc,
  .ga-header-left:focus-within .ga-header-desc {
    grid-template-rows: 1fr;
  }
  .ga-header-desc-inner { overflow: hidden; min-height: 0; }
  .ga-header-desc-text { opacity: 0; transition: opacity 200ms ease; }
  .ga-header-left:hover .ga-header-desc-text,
  .ga-header-left:focus-within .ga-header-desc-text { opacity: 1; }
  @media (prefers-reduced-motion: reduce) {
    .ga-header-expand-btn, .ga-header-desc, .ga-header-desc-text { transition: none !important; }
  }
  @media (prefers-reduced-motion: reduce) {
    .ga-widget-in, .ga-widget-out { animation: none !important; }
    .ga-quick { animation: none !important; }
  }
  /* ===== Input-bar variant ===== */
  /* Docked "Chat Input" bar entrance. */
  @keyframes ga-inbar-bar-in {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  /* Conversation panel grows up from the bar (gentle easeOutQuint for a smooth reveal). */
  @keyframes ga-inbar-panel-in {
    from { opacity: 0; transform: translateY(22px) scale(0.96); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes ga-inbar-panel-out {
    from { opacity: 1; transform: translateY(0) scale(1); }
    to   { opacity: 0; transform: translateY(12px) scale(0.98); }
  }
  /* FAQ chips: fade + rise + slight scale for a soft, springy entrance. */
  @keyframes ga-inbar-faq-in {
    from { opacity: 0; transform: translateY(14px) scale(0.96); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
  }
  /* Individual messages slide in. */
  @keyframes ga-inbar-rise {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .ga-inbar-bar { animation: ga-inbar-bar-in 300ms cubic-bezier(0.16, 1, 0.3, 1) both; }
  .ga-inbar-panel-in  { animation: ga-inbar-panel-in 440ms cubic-bezier(0.22, 1, 0.36, 1) both; }
  .ga-inbar-panel-out { animation: ga-inbar-panel-out 260ms cubic-bezier(0.4, 0, 0.2, 1) both; }
  .ga-inbar-faq { animation: ga-inbar-faq-in 440ms cubic-bezier(0.22, 1, 0.36, 1) both; }
  /* Each direct child of the message list animates in once, when first mounted (React
     keeps existing nodes by key, so only newly appended messages replay it). */
  .ga-inbar-body > * { animation: ga-inbar-rise 320ms cubic-bezier(0.22, 1, 0.36, 1) both; }
  .ga-inbar-faq-btn { transition: filter 0.15s ease, transform 0.15s ease; }
  .ga-inbar-faq-btn:hover { filter: brightness(0.93); transform: translateY(-1px); }
  /* Agent-reply preview card. */
  .ga-inbar-reply { animation: ga-inbar-faq-in 440ms cubic-bezier(0.22, 1, 0.36, 1) both; transition: transform 0.12s ease, box-shadow 0.15s ease; }
  .ga-inbar-reply:hover { transform: translateY(-1px); box-shadow: 0 14px 40px rgba(0, 0, 0, 0.16); }
  @media (prefers-reduced-motion: reduce) {
    .ga-inbar-bar, .ga-inbar-panel-in, .ga-inbar-panel-out, .ga-inbar-faq, .ga-inbar-reply, .ga-inbar-body > * { animation: none !important; }
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
