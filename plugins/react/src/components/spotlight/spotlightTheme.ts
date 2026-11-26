import type React from 'react';
import type { ThemeParams } from '../../styles/genAgentChatStyles';

/** Parse #rgb / #rrggbb / rgb(a)() into 0-255 channels; null when unrecognised. */
export function parseColor(input: string): [number, number, number] | null {
  const value = (input || '').trim().toLowerCase();
  const hex = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/);
  if (hex) {
    const h = hex[1].length === 3 ? hex[1].split('').map((c) => c + c).join('') : hex[1];
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  const rgb = value.match(/^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/);
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
  return null;
}

/** WCAG relative luminance of an sRGB colour. */
function luminance([r, g, b]: [number, number, number]): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/**
 * Text colour that stays legible on `background`: white on dark/saturated fills, near
 * black on light ones. Unknown formats fall back to white (brand colours are usually dark).
 */
export function readableTextOn(background: string): string {
  const rgb = parseColor(background);
  if (!rgb) return '#ffffff';
  const l = luminance(rgb);
  const contrastWhite = 1.05 / (l + 0.05);
  const contrastBlack = (l + 0.05) / 0.05;
  return contrastWhite >= contrastBlack || contrastWhite >= 4.5 ? '#ffffff' : '#111111';
}

/** CSS custom properties the spotlight stylesheet reads, derived from the chat theme. */
export function buildSpotlightVars(t: ThemeParams): React.CSSProperties {
  return {
    ['--gas-primary' as string]: t.primaryColor,
    ['--gas-on-primary' as string]: readableTextOn(t.primaryColor),
    ['--gas-surface' as string]: t.secondaryColor,
    ['--gas-bg' as string]: t.backgroundColor,
    ['--gas-text' as string]: t.textColor,
    ['--gas-muted' as string]: t.mutedTextColor,
    ['--gas-border' as string]: t.borderColor,
    ['--gas-input-bg' as string]: t.inputBackgroundColor,
    ['--gas-font' as string]: t.fontFamily,
    ['--gas-fs' as string]: t.fontSize,
  };
}
