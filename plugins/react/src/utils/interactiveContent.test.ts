import { describe, expect, it } from 'vitest';
import { parseInteractiveContentBlocks } from './interactiveContent';

const reply = 'Sample response:\n```json\n{"id": 42, "name": "Ann"}\n```\nDone.';

describe('parseInteractiveContentBlocks – plain ```json code', () => {
  it('drops non-interactive JSON by default (existing behaviour)', () => {
    expect(parseInteractiveContentBlocks(reply)).toEqual([
      { kind: 'text', text: 'Sample response:' },
      { kind: 'text', text: 'Done.' },
    ]);
  });

  it('keeps it as a fenced code block when asked', () => {
    expect(parseInteractiveContentBlocks(reply, undefined, { keepUnknownJson: true })).toEqual([
      { kind: 'text', text: 'Sample response:' },
      { kind: 'text', text: '```json\n{"id": 42, "name": "Ann"}\n```' },
      { kind: 'text', text: 'Done.' },
    ]);
  });

  it('still turns interactive item lists into widgets', () => {
    const items = '```json\n[{"id": "a", "name": "A"}]\n```';
    const blocks = parseInteractiveContentBlocks(items, undefined, { keepUnknownJson: true });
    expect(blocks.map((b) => b.kind)).not.toContain('text');
  });
});
