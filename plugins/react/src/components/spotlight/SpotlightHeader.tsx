import React, { useEffect, useRef, useState } from 'react';
import { Maximize2, Minimize2, MoreHorizontal, X } from 'lucide-react';
import type { SpotlightController } from './types';
import { spotlightMenuItems } from './SpotlightMenu';

interface SpotlightHeaderProps {
  ctl: SpotlightController;
  menuButtonRef: React.RefObject<HTMLButtonElement>;
}

/**
 * Floating header: round controls in the corners and a centred agent pill. The pill
 * shows logo + name; clicking it pushes it forward slightly and reveals the description.
 * The transcript scrolls underneath and fades out at the top edge.
 */
export const SpotlightHeader: React.FC<SpotlightHeaderProps> = ({ ctl, menuButtonRef }) => {
  const { t } = ctl;
  const [open, setOpen] = useState(false);
  const pillRef = useRef<HTMLButtonElement>(null);
  const canExpand = !ctl.isFullscreen && ctl.windowWidth > 768;
  const hasBrand = ctl.brandLogo.length > 0;
  const hasDescription = !hasBrand && ctl.headerDescription.length > 0;
  // Nothing to offer (no conversation yet on a narrow screen, no languages): no ⋯ button.
  const hasMenu = spotlightMenuItems(ctl).any;
  const expandLabel = ctl.isExpanded ? t('menu.collapse', 'Collapse') : t('menu.expand', 'Expand');

  // Collapse the description again on an outside click.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      if (!pillRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
    };
  }, [open]);

  return (
    <div className="gas-header">
      <div className="gas-header-side">
        <button
          type="button"
          className={`gas-icon-btn${canExpand ? '' : ' gas-icon-btn--hidden'}`}
          onClick={ctl.onExpandToggle}
          title={expandLabel}
          aria-label={expandLabel}
          tabIndex={canExpand ? 0 : -1}
        >
          {ctl.isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
        </button>
      </div>

      <button
        ref={pillRef}
        type="button"
        className={`gas-presence${open ? ' gas-presence--open' : ''}${hasBrand ? ' gas-presence--brand' : ''}`}
        onClick={() => hasDescription && setOpen((o) => !o)}
        aria-expanded={hasDescription ? open : undefined}
        tabIndex={hasDescription ? 0 : -1}
        style={hasDescription ? undefined : { cursor: 'default' }}
      >
        {hasBrand ? (
          <img className="gas-presence-brand" src={ctl.brandLogo} alt={ctl.headerTitle} />
        ) : (
          <>
            <span className="gas-avatar">
              <img src={ctl.logoSrc} alt="" />
            </span>
            <span className="gas-presence-text">
              <span className="gas-presence-title" title={ctl.headerTitle}>{ctl.headerTitle}</span>
              {hasDescription && (
                <span className="gas-presence-sub" aria-hidden={!open}>
                  <span>{ctl.headerDescription}</span>
                </span>
              )}
            </span>
          </>
        )}
      </button>

      <div className="gas-header-side">
        <button
          ref={menuButtonRef}
          type="button"
          className={`gas-icon-btn${hasMenu ? '' : ' gas-icon-btn--hidden'}`}
          tabIndex={hasMenu ? 0 : -1}
          onClick={() => ctl.setShowMenu(!ctl.showMenu)}
          title={t('menu.title', 'Menu')}
          aria-label={t('menu.title', 'Menu')}
          aria-haspopup="menu"
          aria-expanded={ctl.showMenu}
        >
          <MoreHorizontal size={18} />
        </button>
        <button
          type="button"
          className="gas-icon-btn"
          onClick={() => ctl.setOpen(false)}
          title={t('spotlight.close', 'Close chat')}
          aria-label={t('spotlight.close', 'Close chat')}
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
};
