import { describe, expect, it } from 'vitest';

import {
  getPreviewEdgeItems,
  getPreviewRows,
  PREVIEW_ELLIPSIS,
} from '@/views/AIAgents/Workflows/nodeDialogs/training/trainDataSourcePreview';

describe('CSVAnalysisDisplay preview limits', () => {
  it('keeps the first five and last five columns', () => {
    const columns = Array.from({ length: 12 }, (_, index) => `column-${index + 1}`);

    expect(getPreviewEdgeItems(columns, 5)).toEqual([
      'column-1',
      'column-2',
      'column-3',
      'column-4',
      'column-5',
      PREVIEW_ELLIPSIS,
      'column-8',
      'column-9',
      'column-10',
      'column-11',
      'column-12',
    ]);
  });

  it('keeps the first two and last two sample rows', () => {
    const rows = Array.from({ length: 6 }, (_, index) => ({ id: index + 1 }));

    expect(getPreviewEdgeItems(rows, 2)).toEqual([
      { id: 1 },
      { id: 2 },
      PREVIEW_ELLIPSIS,
      { id: 5 },
      { id: 6 },
    ]);
  });

  it('does not duplicate items when the preview is already small', () => {
    expect(getPreviewEdgeItems(['a', 'b', 'c', 'd'], 2)).toEqual([
      'a',
      'b',
      'c',
      'd',
    ]);
  });

  it('shows every bounded SQL preview row without a misleading ellipsis', () => {
    const rows = Array.from({ length: 6 }, (_, index) => ({ id: index + 1 }));

    expect(getPreviewRows(rows, 'query')).toEqual(rows);
    expect(getPreviewRows(rows, 'query')).not.toContain(PREVIEW_ELLIPSIS);
  });

  it('keeps the head and tail treatment for file previews', () => {
    const rows = Array.from({ length: 6 }, (_, index) => ({ id: index + 1 }));

    expect(getPreviewRows(rows, 'file')).toEqual([
      { id: 1 },
      { id: 2 },
      PREVIEW_ELLIPSIS,
      { id: 5 },
      { id: 6 },
    ]);
  });
});
