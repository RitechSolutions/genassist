import { describe, expect, it } from 'vitest';
import type { ChatContentBlock } from '../../types';
import { MAX_TYPING_MS, TYPING_CPS, typingSpeed, withoutOptionSeparators } from './typing';

describe('typingSpeed', () => {
  it('types short replies at the steady pace', () => {
    expect(typingSpeed(90)).toBe(TYPING_CPS);
  });

  it('speeds up long replies so they finish within the cap', () => {
    const total = 1200;
    expect((total / typingSpeed(total)) * 1000).toBeCloseTo(MAX_TYPING_MS);
  });
});

describe('withoutOptionSeparators', () => {
  const opt = (o: string): ChatContentBlock => ({ kind: 'options', options: [o] });
  const text = (t: string): ChatContentBlock => ({ kind: 'text', text: t });

  it('drops separators between suggestions', () => {
    expect(withoutOptionSeparators([text('Answer.'), opt('A'), text(';'), opt('B'), text(' ; '), opt('C')])).toEqual([
      text('Answer.'),
      opt('A'),
      opt('B'),
      opt('C'),
    ]);
  });

  it('drops a trailing separator after the last suggestion', () => {
    expect(withoutOptionSeparators([opt('A'), text('.')])).toEqual([opt('A')]);
  });

  it('keeps real text and punctuation that is not between suggestions', () => {
    const blocks = [text(';'), opt('A'), text('Or ask me anything.'), opt('B')];
    expect(withoutOptionSeparators(blocks)).toEqual(blocks);
  });
});
