export const PREVIEW_ELLIPSIS = Symbol('preview-ellipsis');

export type PreviewEdgeItem<T> = T | typeof PREVIEW_ELLIPSIS;

export type PreviewSource = 'file' | 'query';

export function getPreviewEdgeItems<T>(items: T[], edgeSize: number): PreviewEdgeItem<T>[] {
  if (items.length <= edgeSize * 2) return items;
  return [...items.slice(0, edgeSize), PREVIEW_ELLIPSIS, ...items.slice(-edgeSize)];
}

export function getPreviewRows<T>(
  rows: T[],
  source: PreviewSource,
): PreviewEdgeItem<T>[] {
  // Query previews already contain at most six leading rows. Displaying an
  // ellipsis between them would incorrectly imply they came from both ends of
  // the full query result. File previews contain a real head/tail sample.
  return source === 'query' ? rows : getPreviewEdgeItems(rows, 2);
}
