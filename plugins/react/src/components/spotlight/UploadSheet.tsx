import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, Plus, X } from 'lucide-react';
import { DocFooter, DocThumb } from './DocPreview';
import type { SpotlightController } from './types';

/** Thumbnail for a staged file: the image itself, or a preview of the document. */
const Thumb: React.FC<{ file: File }> = ({ file }) => {
  const isImage = file.type.startsWith('image/');
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!isImage || typeof URL === 'undefined' || !URL.createObjectURL) return;
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file, isImage]);
  // The name is not shown under an image tile; it stays available as alt text and a tooltip.
  if (isImage) return url ? <img src={url} alt={file.name} title={file.name} /> : null;
  return <DocThumb source={{ name: file.name, type: file.type, file }} />;
};

/** Progress ring while uploading, then a check that draws itself in. */
const StatusIcon: React.FC<{ done: boolean }> = ({ done }) =>
  done ? (
    <svg className="gas-sheet-check" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="11" />
      <path d="M7 12.5l3.2 3.2L17 9" />
    </svg>
  ) : (
    <span className="gas-sheet-spinner" aria-hidden="true" />
  );

interface UploadSheetProps {
  ctl: SpotlightController;
  onAddMore: () => void;
}

/**
 * Staged attachments, shown as a sheet that slides up over the transcript: upload
 * progress, thumbnails with remove buttons, an "add more" tile and a send button. It can
 * be collapsed to its header so the visitor can read the conversation while files upload.
 */
export const UploadSheet: React.FC<UploadSheetProps> = ({ ctl, onAddMore }) => {
  const { t } = ctl;
  const [collapsed, setCollapsed] = useState(false);
  const total = ctl.attachments.length;
  const uploading = ctl.attachments.filter((a) => ctl.uploadingFiles.has(a.file.name)).length;
  const done = total - uploading;
  const allDone = uploading === 0;

  // The staged files sit in one row that scrolls sideways; arrows show on a side with more.
  const stripRef = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });
  const updateEdges = useCallback(() => {
    const el = stripRef.current;
    if (!el) return;
    const left = el.scrollLeft > 2;
    const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 2;
    setEdges((prev) => (prev.left === left && prev.right === right ? prev : { left, right }));
  }, []);
  const scrollStrip = (direction: 1 | -1) => {
    const el = stripRef.current;
    if (el) el.scrollBy({ left: direction * el.clientWidth * 0.7, behavior: 'smooth' });
  };

  // New files: bring the end of the row (the newest ones) into view.
  const prevTotal = useRef(total);
  useLayoutEffect(() => {
    const el = stripRef.current;
    if (el && total > prevTotal.current) el.scrollTo({ left: el.scrollWidth, behavior: 'smooth' });
    prevTotal.current = total;
    updateEdges();
  }, [total, updateEdges]);

  useEffect(() => {
    const el = stripRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(updateEdges);
    ro.observe(el);
    return () => ro.disconnect();
  }, [updateEdges]);

  const status = t('spotlight.uploadedCount', '{done} of {total} uploaded')
    .replace('{done}', String(done))
    .replace('{total}', String(total));

  return (
    <div className={`gas-sheet${collapsed ? ' gas-sheet--collapsed' : ''}`} role="region" aria-label={status}>
      <button
        type="button"
        className="gas-sheet-head"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
      >
        <StatusIcon done={allDone} />
        <span className="gas-sheet-status" aria-live="polite">{status}</span>
        <span className="gas-sheet-toggle">
          <ChevronDown size={18} />
        </span>
      </button>

      <div className="gas-sheet-body">
        <div>
          <div className="gas-sheet-strip">
          <div
            ref={stripRef}
            className={`gas-sheet-grid${edges.left ? ' gas-sheet-grid--fade-left' : ''}${edges.right ? ' gas-sheet-grid--fade-right' : ''}`}
            onScroll={updateEdges}
          >
            {ctl.attachments.map((att, i) => {
              const isUploading = ctl.uploadingFiles.has(att.file.name);
              const isDoc = !att.file.type.startsWith('image/');
              return (
                <div
                  key={`${att.file.name}-${att.file.size}`}
                  className={`gas-tile${isDoc ? ' gas-tile--doc' : ''}`}
                  style={{ ['--i' as string]: i }}
                >
                  <div className={`gas-tile-thumb${isUploading ? ' gas-tile-thumb--busy' : ''}`}>
                    <Thumb file={att.file} />
                    {/* Documents carry their type and name in a bar at the bottom of the tile. */}
                    {isDoc && <DocFooter name={att.file.name} type={att.file.type} />}
                    {isUploading && <span className="gas-sheet-spinner gas-tile-spinner" aria-hidden="true" />}
                    <button
                      type="button"
                      className="gas-tile-x"
                      onClick={() => ctl.onRemoveAttachment(att.file.name)}
                      aria-label={t('spotlight.removeFile', 'Remove file')}
                      title={t('spotlight.removeFile', 'Remove file')}
                    >
                      <X size={13} strokeWidth={2.6} />
                    </button>
                  </div>
                </div>
              );
            })}
            <button
              type="button"
              className="gas-tile-add"
              onClick={onAddMore}
              aria-label={t('spotlight.addFile', 'Add a file')}
              title={t('spotlight.addFile', 'Add a file')}
            >
              <Plus size={22} />
            </button>
          </div>
          {edges.left && (
            <button
              type="button"
              className="gas-strip-arrow gas-strip-arrow--left"
              onClick={() => scrollStrip(-1)}
              aria-label={t('spotlight.scrollLeft', 'Scroll left')}
              title={t('spotlight.scrollLeft', 'Scroll left')}
            >
              <ChevronLeft size={18} />
            </button>
          )}
          {edges.right && (
            <button
              type="button"
              className="gas-strip-arrow gas-strip-arrow--right"
              onClick={() => scrollStrip(1)}
              aria-label={t('spotlight.scrollRight', 'Scroll right')}
              title={t('spotlight.scrollRight', 'Scroll right')}
            >
              <ChevronRight size={18} />
            </button>
          )}
          </div>
          <button
            type="button"
            className="gas-btn gas-btn--primary gas-sheet-send"
            disabled={!allDone || ctl.isSendDisabled}
            onClick={ctl.onSubmit}
          >
            {t('spotlight.sendFiles', 'Send files')}
          </button>
        </div>
      </div>
    </div>
  );
};
