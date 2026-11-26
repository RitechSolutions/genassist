import React, { useEffect, useState } from 'react';
import { File as FileGlyph } from 'lucide-react';
import { docKind, docStyle, formatBytes, type DocKind } from './docKind';

/** Where a document's bytes come from: a file the visitor just picked, or an uploaded file's URL. */
export interface DocSource {
  name: string;
  type?: string;
  file?: File;
  url?: string;
}

type Preview = { kind: 'pdf'; src: string } | { kind: 'text'; text: string } | { kind: 'cover' };

const TEXT_PREVIEW_CHARS = 900;

/** The browser can show a PDF inside a frame (desktop Chrome, Edge, Firefox, Safari; not Android). */
const canShowPdf = () =>
  typeof navigator !== 'undefined' && (navigator as Navigator & { pdfViewerEnabled?: boolean }).pdfViewerEnabled === true;

// Uploaded files are fetched once per URL and previewed from memory: no framing of the
// server's URL (so its X-Frame-Options / Content-Disposition can't break the preview).
const remoteCache = new Map<string, Promise<Blob | null>>();
function fetchOnce(url: string): Promise<Blob | null> {
  let pending = remoteCache.get(url);
  if (!pending) {
    pending = fetch(url)
      .then((res) => (res.ok ? res.blob() : null))
      .catch(() => null);
    remoteCache.set(url, pending);
  }
  return pending;
}

function usePreview(source: DocSource, kind: DocKind): Preview | null {
  const [preview, setPreview] = useState<Preview | null>(null);
  const { file, url } = source;

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    const show = (p: Preview) => {
      if (!cancelled) setPreview(p);
    };

    const wantsPdf = kind === 'pdf' && canShowPdf();
    const wantsText = kind === 'text';
    if ((!wantsPdf && !wantsText) || typeof URL === 'undefined') {
      show({ kind: 'cover' });
      return;
    }

    setPreview(null);
    const blobPromise: Promise<Blob | null> = file ? Promise.resolve(file) : url ? fetchOnce(url) : Promise.resolve(null);
    blobPromise
      .then(async (blob) => {
        if (!blob || cancelled) return show({ kind: 'cover' });
        if (wantsText) {
          const text = (await blob.slice(0, TEXT_PREVIEW_CHARS * 4).text()).slice(0, TEXT_PREVIEW_CHARS);
          return show(text.trim() ? { kind: 'text', text } : { kind: 'cover' });
        }
        objectUrl = URL.createObjectURL(blob.type === 'application/pdf' ? blob : new Blob([blob], { type: 'application/pdf' }));
        show({ kind: 'pdf', src: `${objectUrl}#toolbar=0&navpanes=0&scrollbar=0&view=FitH` });
      })
      .catch(() => show({ kind: 'cover' }));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [file, url, kind]);

  return preview;
}

/** The file type as a small coloured file glyph with its extension underneath ("PDF"). */
export const TypeBadge: React.FC<{ name: string; type?: string }> = ({ name, type }) => {
  const { color, label } = docStyle(docKind(name, type), name);
  return (
    <span className="gas-doc-badge" style={{ color }} aria-hidden="true">
      <FileGlyph size={18} strokeWidth={2} />
      <span className="gas-doc-badge-ext">{label.slice(0, 4)}</span>
    </span>
  );
};

/** Type badge + file name (and optional meta line): the bar under a document preview. */
export const DocFooter: React.FC<{ name: string; type?: string; meta?: string }> = ({ name, type, meta }) => (
  <span className="gas-doc-foot">
    <TypeBadge name={name} type={type} />
    <span className="gas-doc-info">
      <span className="gas-doc-name" title={name}>{name}</span>
      {meta && <span className="gas-doc-meta">{meta}</span>}
    </span>
  </span>
);

/**
 * A document's preview, filling its parent: the first page of a PDF, the first lines of a
 * text file, or a cover in the type's colour with its extension when neither can be shown.
 */
export const DocThumb: React.FC<{ source: DocSource }> = ({ source }) => {
  const kind = docKind(source.name, source.type);
  const { color, label } = docStyle(kind, source.name);
  const preview = usePreview(source, kind);
  const [frameReady, setFrameReady] = useState(false);

  return (
    <div className="gas-doc-thumb" style={{ ['--doc-color' as string]: color }}>
      {preview?.kind === 'pdf' && (
        <iframe
          className={`gas-doc-frame${frameReady ? ' gas-doc-frame--ready' : ''}`}
          src={preview.src}
          title=""
          aria-hidden="true"
          tabIndex={-1}
          onLoad={() => setFrameReady(true)}
        />
      )}
      {preview?.kind === 'text' && <pre className="gas-doc-text">{preview.text}</pre>}
      {(preview?.kind === 'cover' || (preview?.kind === 'pdf' && !frameReady)) && (
        <div className="gas-doc-cover">
          <FileGlyph size={30} color={color} />
          <span className="gas-doc-ext">{label}</span>
        </div>
      )}
      {preview === null && <div className="gas-doc-cover gas-doc-cover--loading" />}
    </div>
  );
};

/** A sent document: preview on top, type icon + name + size below; opens the file on click. */
export const DocCard: React.FC<{ source: DocSource; size?: number; openLabel: string }> = ({ source, size, openLabel }) => {
  const kind = docKind(source.name, source.type);
  const { label } = docStyle(kind, source.name);
  const meta = [label, size ? formatBytes(size) : ''].filter(Boolean).join(' · ');
  return (
    <a
      className="gas-doc"
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      title={`${openLabel}: ${source.name}`}
      onClick={(e) => {
        if (!source.url) e.preventDefault();
      }}
    >
      <DocThumb source={source} />
      <DocFooter name={source.name} type={source.type} meta={meta} />
    </a>
  );
};
