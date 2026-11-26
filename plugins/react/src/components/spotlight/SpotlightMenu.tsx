import React, { useEffect, useRef } from 'react';
import { Check, ChevronDown, Fullscreen, Globe, Minimize, RefreshCw } from 'lucide-react';
import type { SpotlightController } from './types';

interface SpotlightMenuProps {
  ctl: SpotlightController;
  /** The ⋯ button, so clicking it toggles instead of counting as an outside click. */
  anchorRef: React.RefObject<HTMLButtonElement>;
}

/** The ⋯ overflow menu: reset, fullscreen, and an inline language accordion. */
/** What the ⋯ menu offers. Reset only once there is a conversation to reset (not while the
 *  Start Conversation button shows); fullscreen on wide screens; languages when the agent has them. */
export function spotlightMenuItems(ctl: Pick<SpotlightController, 'shouldShowStartButton' | 'windowWidth' | 'languages'>) {
  const reset = !ctl.shouldShowStartButton;
  const fullscreen = ctl.windowWidth > 768;
  const languages = ctl.languages.length > 0;
  return { reset, fullscreen, languages, any: reset || fullscreen || languages };
}

export const SpotlightMenu: React.FC<SpotlightMenuProps> = ({ ctl, anchorRef }) => {
  const { t } = ctl;
  const ref = useRef<HTMLDivElement>(null);
  const items = spotlightMenuItems(ctl);
  const showFullscreen = items.fullscreen;
  const hasLanguages = items.languages;
  // The controller is rebuilt every render; read it through a ref so the document
  // listeners subscribe once per open.
  const ctlRef = useRef(ctl);
  ctlRef.current = ctl;

  // Close on an outside click/tap (Escape is handled by the viewport manager).
  useEffect(() => {
    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      const target = e.target as Node;
      if (ref.current?.contains(target) || anchorRef.current?.contains(target)) return;
      ctlRef.current.setShowMenu(false);
      ctlRef.current.setShowLanguageDropdown(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
    };
  }, [anchorRef]);

  // Move focus into the menu so keyboard users land on the first item.
  useEffect(() => {
    ref.current?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true });
  }, []);

  return (
    <div ref={ref} className="gas-popover" role="menu" style={{ top: 54, right: 12 }}>
      {items.reset && (
        <button type="button" role="menuitem" className="gas-menu-item" onClick={ctl.onResetClick}>
          <RefreshCw size={17} />
          <span className="gas-menu-item-label">{t('menu.resetConversation', 'Reset conversation')}</span>
        </button>
      )}
      {showFullscreen && (
        <button type="button" role="menuitem" className="gas-menu-item" onClick={ctl.onFullscreenToggle}>
          {ctl.isFullscreen ? <Minimize size={17} /> : <Fullscreen size={17} />}
          <span className="gas-menu-item-label">
            {ctl.isFullscreen ? t('spotlight.exitFullscreen', 'Exit fullscreen') : t('menu.fullscreen', 'Fullscreen')}
          </span>
        </button>
      )}
      {hasLanguages && (
        <>
          {(items.reset || showFullscreen) && <div className="gas-menu-sep" />}
          <button
            type="button"
            role="menuitem"
            className="gas-menu-item"
            aria-expanded={ctl.showLanguageDropdown}
            onClick={() => ctl.setShowLanguageDropdown(!ctl.showLanguageDropdown)}
          >
            <Globe size={17} />
            <span className="gas-menu-item-label">{t('menu.language', 'Language')}</span>
            <ChevronDown
              size={16}
              className={`gas-menu-chevron${ctl.showLanguageDropdown ? ' gas-menu-chevron--open' : ''}`}
            />
          </button>
          <div className={`gas-submenu${ctl.showLanguageDropdown ? ' gas-submenu--open' : ''}`}>
            <div>
              {ctl.languages.map((lang) => {
                const active = ctl.language === lang.code;
                return (
                  <button
                    key={lang.code}
                    type="button"
                    role="menuitemradio"
                    aria-checked={active}
                    tabIndex={ctl.showLanguageDropdown ? 0 : -1}
                    className={`gas-lang${active ? ' gas-lang--active' : ''}`}
                    onClick={() => {
                      ctl.onLanguageChange(lang.code);
                      ctl.setShowLanguageDropdown(false);
                      ctl.setShowMenu(false);
                    }}
                  >
                    {lang.name}
                    {active && <Check size={15} />}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
