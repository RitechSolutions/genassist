import { describe, expect, it } from 'vitest';
import { docKind, docStyle, formatBytes } from './docKind';

describe('docKind', () => {
  it('reads the MIME type first', () => {
    expect(docKind('report', 'application/pdf')).toBe('pdf');
    expect(docKind('x', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')).toBe('word');
    expect(docKind('x', 'text/plain')).toBe('text');
  });

  it('falls back to the file extension when the type is missing or generic', () => {
    expect(docKind('Firestone_Website.PDF', '')).toBe('pdf');
    expect(docKind('notes.md', 'application/octet-stream')).toBe('text');
    expect(docKind('budget.xlsx')).toBe('sheet');
    expect(docKind('deck.pptx')).toBe('slides');
    expect(docKind('archive.zip')).toBe('other');
  });
});

describe('docStyle', () => {
  it('labels a file by its extension', () => {
    expect(docStyle('word', 'Contract.docx').label).toBe('DOCX');
    expect(docStyle('other', 'no-extension').label).toBe('FILE');
  });
});

describe('formatBytes', () => {
  it('uses the closest unit', () => {
    expect(formatBytes(860)).toBe('860 B');
    expect(formatBytes(12 * 1024)).toBe('12 KB');
    expect(formatBytes(1.4 * 1024 * 1024)).toBe('1.4 MB');
    expect(formatBytes(2 * 1024 * 1024)).toBe('2 MB');
  });
});
