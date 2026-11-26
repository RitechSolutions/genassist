import { describe, expect, it } from 'vitest';
import {
  fitWidth,
  isCaptureCancelled,
  MAX_SCREENSHOT_WIDTH,
  screenshotAllowed,
  screenshotFileName,
} from './screenshot';

describe('screenshot helpers', () => {
  it('names the file after the moment it was taken', () => {
    expect(screenshotFileName(new Date(2026, 10, 5, 9, 3, 7))).toBe('screenshot-2026-11-05-090307.png');
  });

  it('keeps normal captures at full size', () => {
    expect(fitWidth(1920, 1080)).toEqual({ width: 1920, height: 1080 });
  });

  it('scales very wide captures down, keeping the aspect ratio', () => {
    expect(fitWidth(5120, 2880)).toEqual({ width: MAX_SCREENSHOT_WIDTH, height: 1440 });
  });

  it('treats closing the picker as a cancel, not an error', () => {
    expect(isCaptureCancelled({ name: 'NotAllowedError' })).toBe(true);
    expect(isCaptureCancelled({ name: 'AbortError' })).toBe(true);
    expect(isCaptureCancelled({ name: 'NotReadableError' })).toBe(false);
    expect(isCaptureCancelled(null)).toBe(false);
  });

  it('offers screenshots only when the host accepts PNG files', () => {
    expect(screenshotAllowed([])).toBe(true);
    expect(screenshotAllowed(['image/*'])).toBe(true);
    expect(screenshotAllowed(['application/pdf', 'image/png'])).toBe(true);
    expect(screenshotAllowed(['application/pdf'])).toBe(false);
    expect(screenshotAllowed(['image/jpeg'])).toBe(false);
  });
});
