import { useState, useEffect, useMemo } from 'react';

interface UseViewportManagerOptions {
  mode: string;
  widget: boolean;
  isFloatingOpen: boolean;
  showResetConfirm: boolean;
  showLanguageDropdown: boolean;
  showMenu: boolean;
  onExitFullscreen?: () => void;
  setShowResetConfirm: (v: boolean) => void;
  setShowLanguageDropdown: (v: boolean) => void;
  setShowMenu: (v: boolean) => void;
}

export function useViewportManager({
  mode,
  widget,
  isFloatingOpen,
  showResetConfirm,
  showLanguageDropdown,
  showMenu,
  onExitFullscreen,
  setShowResetConfirm,
  setShowLanguageDropdown,
  setShowMenu,
}: UseViewportManagerOptions) {
  const [windowWidth, setWindowWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1024);
  const [windowHeight, setWindowHeight] = useState(typeof window !== 'undefined' ? window.innerHeight : 700);
  const [isFullscreenToggled, setIsFullscreenToggled] = useState(false);

  const isFullscreen = useMemo(() => {
    if (mode === 'fullscreen') return true;
    if (widget) return true;
    if (isFullscreenToggled) return true;
    return windowWidth <= 768;
  }, [windowWidth, widget, isFullscreenToggled, mode]);

  const handleFullscreenToggle = () => {
    setIsFullscreenToggled(prev => !prev);
    setShowMenu(false);
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (mode === 'floating' && !isFloatingOpen) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;

      if (showResetConfirm) {
        e.preventDefault();
        setShowResetConfirm(false);
        return;
      }
      if (showLanguageDropdown) {
        e.preventDefault();
        setShowLanguageDropdown(false);
        return;
      }
      if (showMenu) {
        e.preventDefault();
        setShowMenu(false);
        return;
      }

      if (!isFullscreen) return;

      if (isFullscreenToggled) {
        e.preventDefault();
        setIsFullscreenToggled(false);
        return;
      }
      if (mode === 'fullscreen' && onExitFullscreen) {
        e.preventDefault();
        onExitFullscreen();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [
    isFloatingOpen,
    isFullscreen,
    isFullscreenToggled,
    mode,
    onExitFullscreen,
    showLanguageDropdown,
    showMenu,
    showResetConfirm,
  ]);

  useEffect(() => {
    const updateViewport = () => {
      setWindowWidth(window.innerWidth);
      setWindowHeight(window.innerHeight);
    };
    updateViewport();
    window.addEventListener('resize', updateViewport);
    const vv = typeof window !== 'undefined' ? window.visualViewport : null;
    vv?.addEventListener('resize', updateViewport);
    vv?.addEventListener('scroll', updateViewport);
    return () => {
      window.removeEventListener('resize', updateViewport);
      vv?.removeEventListener('resize', updateViewport);
      vv?.removeEventListener('scroll', updateViewport);
    };
  }, []);

  useEffect(() => {
    if (isFullscreen && typeof document !== 'undefined') {
      const originalStyle = window.getComputedStyle(document.body).overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalStyle;
      };
    }
  }, [isFullscreen]);

  return {
    windowWidth,
    windowHeight,
    isFullscreen,
    isFullscreenToggled,
    handleFullscreenToggle,
  };
}
