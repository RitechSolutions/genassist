export type StatusBadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline' | 'success';

const INDEXING_STATUS = 'indexing';
const SAVE_INDEXED_TYPES = ['text', 'file', 'url'];

export const INDEXING_REFRESH_MS = 5000;
/** A row that reads Indexing for longer than this is no longer followed. */
export const INDEXING_FOLLOW_LIMIT_MS = 10 * 60 * 1000;

interface IndexingRow {
  type?: string | null;
  last_sync_status?: string | null;
  last_synced?: string | null;
}

export function syncStatusBadgeVariant(status: string): StatusBadgeVariant {
  const s = status.toLowerCase();
  if (s === 'error' || s.includes('fail')) return 'destructive';
  if (s.includes('warning')) return 'secondary';
  if (s === 'success') return 'success';
  return 'outline';
}

export function isSyncErrorStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  const s = status.toLowerCase();
  return s === 'error' || s.includes('fail');
}

export function isIndexingStatus(status: string | null | undefined): boolean {
  return status?.toLowerCase() === INDEXING_STATUS;
}

/** Knowledge bases whose documents are indexed when they are saved, not by a sync. */
export function isIndexedOnSave(type: string | null | undefined): boolean {
  return SAVE_INDEXED_TYPES.includes(type ?? '');
}

/** The status in plain words; a value this page does not know is shown as it is. */
export function knowledgeBaseStatusLabel(status: string): string {
  if (isSyncErrorStatus(status)) return 'Failed';
  if (isIndexingStatus(status)) return 'Indexing';
  const s = status.toLowerCase();
  if (s.includes('warning')) return 'Ready with warnings';
  if (s === 'success') return 'Ready';
  return status;
}

function startedIndexingRecently(row: IndexingRow, now: number): boolean {
  const startedAt = Date.parse(row.last_synced ?? '');
  return Number.isFinite(startedAt) && now - startedAt < INDEXING_FOLLOW_LIMIT_MS;
}

/** How often the list reloads: while a row started indexing recently, otherwise not at all. */
export function indexingRefreshInterval(rows: IndexingRow[] | undefined, now: number = Date.now()): number | false {
  const isFollowed = (row: IndexingRow) =>
    isIndexedOnSave(row.type) && isIndexingStatus(row.last_sync_status) && startedIndexingRecently(row, now);
  return (rows ?? []).some(isFollowed) ? INDEXING_REFRESH_MS : false;
}
