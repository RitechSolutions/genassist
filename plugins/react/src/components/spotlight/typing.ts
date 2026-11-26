import type { ChatContentBlock } from '../../types';

/** Typing pace for a reply that arrives whole, in (rendered) characters per second. */
export const TYPING_CPS = 90;
/** Long replies speed up so typing never takes longer than this. */
export const MAX_TYPING_MS = 3000;

/** Characters per second for a reply of `total` characters. */
export function typingSpeed(total: number): number {
  return Math.max(TYPING_CPS, (total * 1000) / MAX_TYPING_MS);
}

/** Punctuation an agent puts between its ***suggestions*** ("Q1; Q2", "Q1 | Q2"). */
const SEPARATOR_ONLY = /^[\s;,.|/•·\-–—]*$/;

/**
 * Drops text blocks that are only separators between two suggestion blocks, so a reply
 * written as `***A***; ***B***` shows its suggestions without a stray ";" between them.
 */
export function withoutOptionSeparators(blocks: ChatContentBlock[]): ChatContentBlock[] {
  return blocks.filter((block, i) => {
    if (block.kind !== 'text' || !SEPARATOR_ONLY.test(block.text)) return true;
    const prev = blocks[i - 1];
    const next = blocks[i + 1];
    return !(prev?.kind === 'options' && (!next || next.kind === 'options'));
  });
}
