/** What a document preview can do with a file, from its MIME type or, failing that, its name. */
export type DocKind = 'pdf' | 'text' | 'word' | 'sheet' | 'slides' | 'other';

const extensionOf = (name: string) => {
  const base = name.split(/[\\/]/).pop() || '';
  const dot = base.lastIndexOf('.');
  return dot > 0 ? base.slice(dot + 1).toLowerCase() : '';
};

export function docKind(name: string, type?: string): DocKind {
  const mime = (type || '').toLowerCase();
  const ext = extensionOf(name);
  if (mime === 'application/pdf' || ext === 'pdf') return 'pdf';
  if (mime.includes('wordprocessingml') || mime === 'application/msword' || ['doc', 'docx', 'odt', 'rtf'].includes(ext)) return 'word';
  if (mime.includes('spreadsheetml') || mime === 'application/vnd.ms-excel' || ['xls', 'xlsx', 'ods'].includes(ext)) return 'sheet';
  if (mime.includes('presentationml') || ['ppt', 'pptx', 'odp'].includes(ext)) return 'slides';
  if (mime.startsWith('text/') || mime === 'application/json' || ['txt', 'md', 'csv', 'json', 'log'].includes(ext)) return 'text';
  return 'other';
}

const COLORS: Record<DocKind, string> = {
  pdf: '#DC2626',
  word: '#2563EB',
  sheet: '#16A34A',
  slides: '#EA580C',
  text: '#64748B',
  other: '#64748B',
};

/** The type's colour and the short label shown on its cover and in the card footer ("PDF", "DOCX"). */
export function docStyle(kind: DocKind, name: string): { color: string; label: string } {
  const ext = extensionOf(name);
  return { color: COLORS[kind], label: (ext || (kind === 'other' ? 'file' : kind)).toUpperCase() };
}

/** "860 B", "12 KB", "1.4 MB" */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(/\.0$/, '')} MB`;
}
