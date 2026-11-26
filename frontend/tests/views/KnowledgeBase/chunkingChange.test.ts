import { describe, it, expect } from 'vitest';

import { isChunkStrategyChanged } from '@/views/KnowledgeBase/utils/chunkingChange';

const withStrategy = (strategy?: string) => ({ vector: { enabled: true, chunk_strategy: strategy } });

describe('chunking strategy change', () => {
  it('is a change when another strategy is selected', () => {
    expect(isChunkStrategyChanged(withStrategy('recursive'), withStrategy('sections'))).toBe(true);
  });

  it('is no change when the saved strategy is selected again', () => {
    expect(isChunkStrategyChanged(withStrategy('sections'), withStrategy('sections'))).toBe(false);
  });

  it('reads a knowledge base saved without a strategy as the default one', () => {
    const savedWithoutStrategy = { vector: { enabled: true } };

    expect(isChunkStrategyChanged(savedWithoutStrategy, withStrategy('recursive'))).toBe(false);
    expect(isChunkStrategyChanged(savedWithoutStrategy, withStrategy('sections'))).toBe(true);
  });

  it.each([null, undefined])('is no change for a knowledge base that was never saved (%s)', (savedRagConfig) => {
    expect(isChunkStrategyChanged(savedRagConfig, withStrategy('sections'))).toBe(false);
  });
});
