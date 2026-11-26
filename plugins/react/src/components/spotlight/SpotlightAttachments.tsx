import React, { useState } from 'react';
import type { Attachment } from '../../types';
import { DocCard } from './DocPreview';
import type { SpotlightController } from './types';

/** Tiles shown before the rest collapse into a "+n" tile. */
const VISIBLE_TILES = 3;

const isImage = (a: Attachment) => Boolean(a.url) && (a.type || '').startsWith('image/');

/** One image: whole, at its own aspect ratio. Falls back to the file card if it fails to load. */
const ImageView: React.FC<{
  attachment: Attachment;
  className: string;
  onBroken: () => void;
  overlay?: React.ReactNode;
  onClick?: (e: React.MouseEvent) => void;
}> = ({ attachment, className, onBroken, overlay, onClick }) => {
  const [loaded, setLoaded] = useState(false);
  return (
    <a
      className={`gas-media ${className}${loaded ? ' gas-media--loaded' : ''}`}
      href={attachment.url}
      target="_blank"
      rel="noopener noreferrer"
      title={attachment.name}
      onClick={onClick}
    >
      <img src={attachment.url} alt={attachment.name} loading="lazy" onLoad={() => setLoaded(true)} onError={onBroken} />
      {overlay}
    </a>
  );
};

/**
 * A message's attachments: images as pictures (one whole; several as a row of tiles, with
 * a "+n" tile past three that expands the rest), other files as file cards.
 */
export const SpotlightAttachments: React.FC<{
  ctl: SpotlightController;
  attachments: Attachment[];
  align: 'start' | 'end';
  spaced: boolean;
}> = ({ ctl, attachments, align, spaced }) => {
  const [broken, setBroken] = useState<Set<number>>(() => new Set());
  const [expanded, setExpanded] = useState(false);

  const markBroken = (index: number) =>
    setBroken((prev) => {
      const next = new Set(prev);
      next.add(index);
      return next;
    });

  const indexed = attachments.map((attachment, index) => ({ attachment, index }));
  const images = indexed.filter(({ attachment, index }) => isImage(attachment) && !broken.has(index));
  const files = indexed.filter(({ attachment, index }) => !isImage(attachment) || broken.has(index));

  const collapsed = !expanded && images.length > VISIBLE_TILES;
  const shown = collapsed ? images.slice(0, VISIBLE_TILES + 1) : images;
  const hiddenCount = images.length - VISIBLE_TILES;

  return (
    <div className={`gas-attachments gas-attachments--${align}${spaced ? ' gas-attachments--spaced' : ''}`}>
      {images.length === 1 && (
        <ImageView
          attachment={images[0].attachment}
          className="gas-media--single"
          onBroken={() => markBroken(images[0].index)}
        />
      )}

      {images.length > 1 && (
        <div className={`gas-media-grid gas-media-grid--${Math.min(shown.length, 4)}${expanded ? ' gas-media-grid--all' : ''}`}>
          {shown.map(({ attachment, index }, position) => {
            const isMoreTile = collapsed && position === VISIBLE_TILES;
            return (
              <ImageView
                key={index}
                attachment={attachment}
                className="gas-media--tile"
                onBroken={() => markBroken(index)}
                overlay={isMoreTile ? <span className="gas-media-more">+{hiddenCount}</span> : undefined}
                onClick={
                  isMoreTile
                    ? (e) => {
                        e.preventDefault();
                        setExpanded(true);
                      }
                    : undefined
                }
              />
            );
          })}
        </div>
      )}

      {files.map(({ attachment, index }) => (
        <DocCard
          key={index}
          source={{ name: attachment.name, type: attachment.type, url: attachment.url }}
          size={attachment.size}
          openLabel={ctl.t('spotlight.openFile', 'Open')}
        />
      ))}
    </div>
  );
};
