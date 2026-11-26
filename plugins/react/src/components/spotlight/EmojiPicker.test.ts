import { describe, expect, it } from 'vitest';
import { insertAtSelection, SPOTLIGHT_EMOJIS } from './EmojiPicker';

describe('insertAtSelection', () => {
  it('inserts at the caret and puts the caret after the emoji', () => {
    expect(insertAtSelection('hi there', '🙂', 2, 2)).toEqual({ value: 'hi🙂 there', caret: 4 });
  });

  it('replaces selected text', () => {
    expect(insertAtSelection('I am sad', '😢', 5, 8)).toEqual({ value: 'I am 😢', caret: 7 });
  });

  it('appends to an empty or untouched field', () => {
    expect(insertAtSelection('', '👍', 0, 0)).toEqual({ value: '👍', caret: 2 });
  });

  it('clamps a stale selection that is past the end of the text', () => {
    expect(insertAtSelection('ok', '🎉', 10, 12)).toEqual({ value: 'ok🎉', caret: 4 });
  });
});

describe('SPOTLIGHT_EMOJIS', () => {
  it('fills two rows of eight with no duplicates', () => {
    expect(SPOTLIGHT_EMOJIS).toHaveLength(16);
    expect(new Set(SPOTLIGHT_EMOJIS).size).toBe(16);
  });
});
