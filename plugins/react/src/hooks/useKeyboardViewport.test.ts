import { describe, expect, it } from 'vitest';
import { KEYBOARD_CLOSED, keyboardViewport, sameKeyboardViewport, type ViewportSample } from './useKeyboardViewport';
import {
  getContainerStyle,
  getFloatingContainerStyle,
  getFloatingShellStyle,
  getInputBarPanelStyle,
  getInputBarRootStyle,
  keyboardFitStyle,
  type ThemeParams,
} from '../styles/genAgentChatStyles';

// An iPhone-sized screen: 844px tall, a 336px keyboard leaves 508px visible.
const typing: ViewportSample = { layoutHeight: 844, visualHeight: 508, visualTop: 0, scale: 1, chatFieldFocused: true };

describe('keyboardViewport', () => {
  it('reports the visible area and what the keyboard covers', () => {
    expect(keyboardViewport(typing)).toEqual({ open: true, top: 0, height: 508, inset: 336 });
  });

  it('follows the page when the browser has panned it to the field', () => {
    // iOS scrolls the visual viewport down; the area under the keyboard shrinks by as much.
    expect(keyboardViewport({ ...typing, visualTop: 120.4 })).toEqual({ open: true, top: 120, height: 508, inset: 216 });
  });

  it('stays closed when the field is not the chat’s own', () => {
    expect(keyboardViewport({ ...typing, chatFieldFocused: false })).toBe(KEYBOARD_CLOSED);
  });

  it('ignores toolbars showing or hiding (a small difference) and pinch zoom', () => {
    expect(keyboardViewport({ ...typing, visualHeight: 770 })).toBe(KEYBOARD_CLOSED);
    expect(keyboardViewport({ ...typing, scale: 2 })).toBe(KEYBOARD_CLOSED);
  });

  it('stays closed when the browser already shrank the page for the keyboard', () => {
    // interactive-widget=resizes-content: layout and visual heights shrink together.
    expect(keyboardViewport({ ...typing, layoutHeight: 508 })).toBe(KEYBOARD_CLOSED);
  });

  it('compares readings by value', () => {
    expect(sameKeyboardViewport(keyboardViewport(typing), keyboardViewport(typing))).toBe(true);
    expect(sameKeyboardViewport(keyboardViewport(typing), KEYBOARD_CLOSED)).toBe(false);
  });
});

const open = keyboardViewport(typing);
const theme = { borderColor: '#eee', secondaryColor: '#fff', fontFamily: 'x' } as ThemeParams;

describe('keyboard-aware layout', () => {
  it('fits a full-screen chat to the area above the keyboard', () => {
    expect(keyboardFitStyle(open)).toEqual({ top: 0, bottom: 'auto', height: 508, maxHeight: 508 });
    expect(keyboardFitStyle(KEYBOARD_CLOSED)).toEqual({});

    const full = getContainerStyle({ isFullscreen: true, isFloatingDocked: false, windowWidth: 390, t: theme, keyboard: open });
    expect(full).toMatchObject({ position: 'fixed', top: 0, bottom: 'auto', height: 508 });

    const wrapper = getFloatingContainerStyle({
      mode: 'floating', isFullscreen: true, windowWidth: 390, windowHeight: 844,
      position: 'bottom-right', offsetX: 20, offsetY: 20, keyboard: { ...open, top: 120 },
    });
    expect(wrapper).toMatchObject({ top: 120, bottom: 'auto', height: 508 });
  });

  it('leaves the layout alone while the keyboard is down', () => {
    const full = getContainerStyle({ isFullscreen: true, isFloatingDocked: false, windowWidth: 390, t: theme, keyboard: KEYBOARD_CLOSED });
    expect(full).toMatchObject({ top: 0, bottom: 'env(safe-area-inset-bottom, 0px)' });
    expect(full.height).toBeUndefined();
    // An inline (not full-screen) chat is never moved.
    const inline = getContainerStyle({ isFullscreen: false, isFloatingDocked: false, windowWidth: 1200, t: theme, keyboard: open });
    expect(inline.top).toBeUndefined();
  });

  it('sits a docked widget on the keyboard and fits it in the space above', () => {
    const shell = getFloatingShellStyle({ windowHeight: 1024, offsetY: 20, position: 'bottom-right', keyboard: { ...open, height: 640, inset: 384 } });
    expect(shell.bottom).toBe(20 + 384);
    expect(shell.height).toBe(640 - 20 - 20);
    expect(shell.maxHeight).toBe(640 - 20 - 20);
  });

  it('lifts the input bar onto the keyboard and caps its panel to the room left', () => {
    expect(getInputBarRootStyle('x', 24, open).bottom).toBe(12 + 336);
    expect(getInputBarRootStyle('x', 24, KEYBOARD_CLOSED).bottom).toBe(24);
    expect(getInputBarPanelStyle('#fff', '#eee', 400).height).toBe('min(70vh, 520px, 400px)');
    expect(getInputBarPanelStyle('#fff', '#eee').height).toBe('min(70vh, 520px)');
  });
});
