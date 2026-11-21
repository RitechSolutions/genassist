import { RagConfigValues } from '../types/ragSchema';

const DEFAULT_CHUNK_STRATEGY = 'recursive';

export const CHUNKING_CHANGE_NOTE =
  'The chunking strategy was changed. It takes effect when the content is indexed again: on save for uploaded content, at the next sync for connected sources.';

function chunkStrategyOf(ragConfig: RagConfigValues | null | undefined): string {
  const strategy = ragConfig?.vector?.chunk_strategy;
  const hasStrategy = typeof strategy === 'string' && strategy !== '';
  return hasStrategy ? strategy : DEFAULT_CHUNK_STRATEGY;
}

/** True when the selected chunking strategy differs from the one the knowledge base was saved with. */
export function isChunkStrategyChanged(
  savedRagConfig: RagConfigValues | null | undefined,
  currentRagConfig: RagConfigValues | null | undefined
): boolean {
  const isSavedKnowledgeBase = savedRagConfig != null;
  return isSavedKnowledgeBase && chunkStrategyOf(savedRagConfig) !== chunkStrategyOf(currentRagConfig);
}
