import React, { useState, useRef, useEffect, useLayoutEffect, useMemo, useCallback } from 'react';
import { ChatMessageComponent } from './ChatMessage';
import { AttachmentPreview } from './common/AttachmentPreview';
import { useChat } from '../hooks/useChat';
import { useScrollManagement } from '../hooks/useScrollManagement';
import { useThinkingAnimation } from '../hooks/useThinkingAnimation';
import { useViewportManager } from '../hooks/useViewportManager';
import { useFileAttachments } from '../hooks/useFileAttachments';
import { ChatMessage, GenAgentChatProps, ScheduleItem } from '../types';
import { VoiceInput } from './VoiceInput';
import { AudioService } from '../services/audioService';
import { Paperclip, MoreVertical, RefreshCw, Globe, X, ArrowUp, Maximize2, Minimize2, AlertCircle } from 'lucide-react';
import { ChatBubble } from './ChatBubble';
import DynamicFormMessage from './DynamicFormMessage';
import { LanguageSelector } from './LanguageSelector';
import chatLogo from '../assets/chat-logo.png';

import {
  resolveLanguage,
  mergeTranslations,
  getTranslationString,
  getTranslationsForLanguage,
} from '../utils/i18n';
import { GoogleReCaptcha, GoogleReCaptchaProvider } from 'react-google-recaptcha-v3';

import {
  resolveTheme,
  hexToRgba,
  getContainerStyle,
  getHeaderStyle,
  logoContainerStyle,
  logoStyle,
  headerTitleContainerStyle,
  getHeaderTitleStyle,
  getHeaderSubtitleStyle,
  menuButtonStyle,
  getMenuPopupStyle,
  getMenuItemStyle,
  chatContainerStyle,
  inputContainerStyle,
  inputWrapperStyle,
  getTextAreaStyle,
  attachButtonStyle,
  getSendButtonStyle,
  sendButtonDisabledStyle,
  rightActionContainerStyle,
  getPossibleQueriesContainerStyle,
  getQueryButtonStyle,
  getConfirmOverlayStyle,
  getConfirmDialogStyle,
  confirmButtonsStyle,
  getConfirmButtonStyle,
  getContentCardStyle,
  getDisclaimerStyle,
  getPositionStyles,
  getFloatingContainerStyle,
  CSS_KEYFRAMES,
} from '../styles/genAgentChatStyles';

const SHOW_CHAT_LANGUAGE_SELECTOR = true;

export const GenAgentChat: React.FC<GenAgentChatProps> = ({
  baseUrl,
  websocketUrl,
  apiKey,
  tenant,
  metadata,
  useWs = true,
  usePoll = false,
  onError,
  onTakeover,
  onFinalize,
  theme,
  headerTitle = 'Genassist',
  description,
  placeholder,
  agentName,
  logoUrl,
  mode = 'embedded',
  onExitFullscreen,
  floatingConfig = {},
  language,
  translations: customTranslations,
  reCaptchaKey,
  widget = false,
  useAudio = false,
  useFile = false,
  noColorAnimation = false,
  showWelcomeBeforeStart = true,
  allowedExtensions = [],
  serverUnavailableMessage,
  serverUnavailableContactUrl,
  serverUnavailableContactLabel,
  formDisplay = 'footer',
  onConfigLoaded,
}): React.ReactElement => {
  // Language selection state (with localStorage persistence)
  const [selectedLanguage, setSelectedLanguage] = useState<string>(() => {
    if (language) return language;
    const stored = typeof window !== 'undefined' ? localStorage.getItem('genassist_language') : null;
    if (stored) return stored;
    return resolveLanguage();
  });

  // Save language to localStorage when it changes
  useEffect(() => {
    if (typeof window !== 'undefined' && !language) {
      localStorage.setItem('genassist_language', selectedLanguage);
    }
  }, [selectedLanguage, language]);

  // State for tracking selected FAQ query
  const [selectedFaqQuery, setSelectedFaqQuery] = useState<string | null>(null);

  // Resolve language: prop > selected > browser > 'en'
  const resolvedLanguage = useMemo(() => {
    if (language) return language;
    return selectedLanguage || resolveLanguage() || 'en';
  }, [language, selectedLanguage]);

  // Merge language and FAQ query into metadata
  const metadataWithLanguage = useMemo(() => {
    return {
      ...(metadata || {}),
      language: resolvedLanguage,
      ...(selectedFaqQuery ? { faq_query: selectedFaqQuery } : {}),
    };
  }, [metadata, resolvedLanguage, selectedFaqQuery]);

  // Get translations based on resolved language, then merge with custom translations
  const translations = useMemo(() => {
    const baseTranslations = getTranslationsForLanguage(resolvedLanguage);
    return mergeTranslations(customTranslations, baseTranslations);
  }, [resolvedLanguage, customTranslations]);

  const t = (key: string, fallback?: string): string => {
    return getTranslationString(key, translations, fallback);
  };

  const inputPlaceholder = useMemo(() => placeholder || t('input.placeholder', 'Ask a question'), [placeholder, translations]);
  const [inputValue, setInputValue] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showLanguageDropdown, setShowLanguageDropdown] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [isFloatingOpen, setIsFloatingOpen] = useState(false);
  const [submittedForms, setSubmittedForms] = useState<Set<number>>(new Set());
  const [submittingFormIndex, setSubmittingFormIndex] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const [headerHeight, setHeaderHeight] = useState(56);
  const [showBacklight, setShowBacklight] = useState(false);

  const {
    messages,
    isLoading,
    sendMessage,
    sendAudioMessage,
    uploadFile,
    resetConversation,
    startConversation,
    conversationId,
    guestToken,
    possibleQueries,
    isFinalized,
    isAgentTyping,
    addFeedback,
    availableLanguages: agentAvailableLanguages,
    welcomeTitle,
    welcomeImageUrl,
    welcomeMessage,
    inputDisclaimerHtml,
    thinkingPhrases,
    thinkingDelayMs,
  } = useChat({
    baseUrl,
    websocketUrl,
    apiKey,
    tenant,
    metadata: metadataWithLanguage,
    useWs,
    usePoll,
    language: resolvedLanguage,
    onError,
    onTakeover,
    onFinalize,
    serverUnavailableMessage,
    serverUnavailableContactUrl,
    serverUnavailableContactLabel,
    onConfigLoaded,
  });

  const { currentThinkingParts, currentThinkingPartIndex } = useThinkingAnimation({
    isAgentTyping,
    thinkingPhrases,
    thinkingDelayMs,
    translations,
  });

  const { messagesEndRef, chatContainerRef } = useScrollManagement({
    messages,
    isAgentTyping,
    currentThinkingPartIndex,
    currentThinkingPartsLength: currentThinkingParts.length,
    conversationId,
    isFloatingOpen,
    mode,
  });

  const {
    windowWidth,
    windowHeight,
    isFullscreen,
    handleFullscreenToggle,
  } = useViewportManager({
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
  });

  const {
    attachments,
    setAttachments,
    uploadingFiles,
    fileErrorToast,
    fileInputRef,
    handleFileChange,
    handleRemoveAttachment,
    clearAttachments,
  } = useFileAttachments({ uploadFile, t });

  useEffect(() => {
    if (language) return;
    if (!Array.isArray(agentAvailableLanguages) || agentAvailableLanguages.length === 0) {
      return;
    }
    const normalized = agentAvailableLanguages.map((lang) => lang.toLowerCase());
    if (!normalized.includes(selectedLanguage.toLowerCase())) {
      setSelectedLanguage(normalized[0]);
    }
  }, [agentAvailableLanguages, language, selectedLanguage]);

  const audioService = useRef<AudioService | null>(null);
  const reCaptchaTokenRef = useRef<string | undefined>(undefined);

  const hasUserMessages = messages.some(message => message.speaker === 'customer');

  useEffect(() => {
    audioService.current = new AudioService({ baseUrl, websocketUrl, apiKey });
  }, [baseUrl, websocketUrl, apiKey]);

  useEffect(() => {
    audioService.current?.setGuestToken(guestToken ?? null);
  }, [guestToken]);

  useEffect(() => {
    if (mode === 'fullscreen' && !isFloatingOpen) {
      setIsFloatingOpen(true);
    }
  }, [mode, isFloatingOpen]);

  useLayoutEffect(() => {
    const updateHeaderHeight = () => {
      setHeaderHeight(headerRef.current?.offsetHeight || 56);
    };
    updateHeaderHeight();
    const resizeObserver = new ResizeObserver(() => updateHeaderHeight());
    if (headerRef.current) {
      resizeObserver.observe(headerRef.current);
    }
    window.addEventListener('resize', updateHeaderHeight);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateHeaderHeight);
    };
  }, []);

  useEffect(() => {
    if (isAgentTyping) {
      setShowBacklight(true);
      return;
    }
    const timer = setTimeout(() => setShowBacklight(false), 420);
    return () => clearTimeout(timer);
  }, [isAgentTyping]);

  const submitMessage = async () => {
    if (inputValue.trim() === '' && attachments.length === 0) return;
    if (isAgentTyping) return;
    const textToSend = inputValue;
    const filesToUpload = attachments.map(a => a.file);

    setInputValue('');
    setAttachments([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    try {
      const extraMetadata: Record<string, any> = {};

      if (selectedFaqQuery) {
        extraMetadata.faq_query = selectedFaqQuery;
      }

      if (filesToUpload.length > 0) {
        extraMetadata.attachments = attachments.map(a => a.attachment);
      }

      await sendMessage(textToSend, filesToUpload, extraMetadata, reCaptchaTokenRef.current);
    } catch (error) {
      // ignore
    } finally {
      setTimeout(() => textAreaRef.current?.focus(), 0);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitMessage();
  };

  const getFormNodeId = (messageIndex: number): string | undefined => {
    const msg = messages[messageIndex];
    if (msg?.type === 'form_request' && msg.text) {
      try { return JSON.parse(msg.text).node_id; } catch { /* skip */ }
    }
    return undefined;
  };

  const handleFormSubmit = async (formData: Record<string, unknown>, messageIndex: number) => {
    if (submittingFormIndex !== null || isAgentTyping) return;
    setSubmittingFormIndex(messageIndex);
    try {
      const summaryText = Object.entries(formData)
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ');
      const nodeId = getFormNodeId(messageIndex);
      await sendMessage(summaryText, [], {
        human_in_the_loop_from_form: formData,
        ...(nodeId && { human_in_the_loop_node_id: nodeId }),
      }, reCaptchaTokenRef.current);
      setSubmittedForms((prev) => new Set(prev).add(messageIndex));
    } catch (error) {
      // ignore
    } finally {
      setSubmittingFormIndex(null);
    }
  };

  const handleFormCancel = async (messageIndex: number) => {
    if (submittingFormIndex !== null || isAgentTyping) return;
    setSubmittingFormIndex(messageIndex);
    try {
      const nodeId = getFormNodeId(messageIndex);
      await sendMessage('Skipped', [], {
        human_in_the_loop_from_form: {},
        human_in_the_loop_cancelled: true,
        ...(nodeId && { human_in_the_loop_node_id: nodeId }),
      }, reCaptchaTokenRef.current);
      setSubmittedForms((prev) => new Set(prev).add(messageIndex));
    } catch (error) {
      // ignore
    } finally {
      setSubmittingFormIndex(null);
    }
  };

  const handleQuickAction = async (text: string) => {
    if (!text.trim()) return;
    if (isAgentTyping) return;
    try {
      const extraMetadata = selectedFaqQuery ? { faq_query: selectedFaqQuery } : undefined;
      await sendMessage(text, [], extraMetadata, reCaptchaTokenRef.current);
    } catch (error) {
      // ignore quick action errors to avoid interrupting the flow
    }
  };

  const handleScheduleConfirm = async (schedule: ScheduleItem) => {
    const summary = `Schedule confirmed with ${schedule.restaurants.length} restaurants`;
    try {
      await sendMessage(summary, [], { confirmSchedule: JSON.stringify(schedule) }, reCaptchaTokenRef.current);
    } catch (error) {
      // ignore
    }
  };

  const handleVoiceError = (error: Error) => {
    if (onError) {
      onError(error);
    }
  };

  const playResponseAudio = async (text: string) => {
    if (!audioService.current || isPlayingAudio) return;

    try {
      setIsPlayingAudio(true);
      const audioBlob = await audioService.current.textToSpeech(text);
      await audioService.current.playAudio(audioBlob);
    } catch (error) {
      if (onError) {
        onError(error as Error);
      }
    } finally {
      setIsPlayingAudio(false);
    }
  };

  const audioUrlBuilder = useCallback((messageId: string) => {
    return `${baseUrl}/api/conversations/${conversationId}/messages/${messageId}/audio`;
  }, [baseUrl, conversationId]);

  const audioHeaders = useMemo(() => {
    const h: Record<string, string> = {};
    if (guestToken) {
      h['Authorization'] = `Bearer ${guestToken}`;
    } else {
      h['x-api-key'] = apiKey;
    }
    if (tenant) h['x-tenant-id'] = tenant;
    return h;
  }, [apiKey, tenant, guestToken]);

  const [autoPlayAudioMessageId, setAutoPlayAudioMessageId] = useState<string | null>(null);
  const prevMessageCountRef = useRef<number>(0);
  const initialLoadDoneRef = useRef(false);
  React.useEffect(() => {
    if (!useAudio || !messages.length) return;
    const prevCount = prevMessageCountRef.current;
    prevMessageCountRef.current = messages.length;
    if (!initialLoadDoneRef.current) {
      initialLoadDoneRef.current = true;
      return;
    }
    if (messages.length <= prevCount) return;
    const last = messages[messages.length - 1];
    if (last.speaker === 'agent' && last.type === 'audio' && last.message_id) {
      setAutoPlayAudioMessageId(last.message_id);
    }
  }, [messages, useAudio]);

  const handleQueryClick = async (query: string) => {
    if (isAgentTyping || isLoading) return;

    setSelectedFaqQuery(query);

    try {
      await sendMessage(query, [], { faq_query: query }, reCaptchaTokenRef.current);
    } catch (error) {
      // ignore
    }
  };

  const handleStartConversation = async () => {
    if (isLoading) return;

    setInputValue('');
    clearAttachments();

    try {
      await startConversation(reCaptchaTokenRef.current);
    } catch (error) {
      console.error('Error starting conversation', error);
    }
  };

  const handleMenuClick = () => {
    setShowMenu(prev => !prev);
  };

  const handleResetClick = () => {
    setShowMenu(false);
    setShowResetConfirm(true);
  };

  const handleConfirmReset = async () => {
    setInputValue('');
    clearAttachments();

    await resetConversation(reCaptchaTokenRef.current);
    setSelectedFaqQuery(null);
    setSubmittedForms(new Set());
    setSubmittingFormIndex(null);
    setShowResetConfirm(false);
  };

  const handleCancelReset = () => {
    setShowResetConfirm(false);
  };

  const handleLanguageChange = (lang: string) => {
    setSelectedLanguage(lang);
  };

  const handleReCaptchaVerify = useCallback((token: string) => {
    reCaptchaTokenRef.current = token;
  }, []);

  const allLanguages = [
    { code: 'en', name: 'English' },
    { code: 'es', name: 'Español' },
    { code: 'fr', name: 'Français' },
    { code: 'de', name: 'Deutsch' },
    { code: 'it', name: 'Italiano' },
    { code: 'pt', name: 'Português' },
    { code: 'zh', name: '中文' },
  ];
  const availableLanguages = useMemo(() => {
    if (Array.isArray(agentAvailableLanguages)) {
      const allowed = new Set(
        agentAvailableLanguages.map((lang) => lang.toLowerCase()),
      );
      return allLanguages.filter((lang) => allowed.has(lang.code));
    }
    return allLanguages;
  }, [agentAvailableLanguages]);
  const hasLanguageOptions = availableLanguages.length > 0;

  // Resolve theme values
  const themeParams = resolveTheme(theme);
  const { primaryColor, backgroundColor, textColor, fontFamily, fontSize } = themeParams;
  const fontSizeNumber = typeof fontSize === 'string' ? parseInt(fontSize, 10) : (typeof fontSize === 'number' ? fontSize : 14);

  const position = floatingConfig.position || 'bottom-right';
  const offset = floatingConfig.offset || { x: 20, y: 20 };
  const offsetX = offset.x || 20;
  const offsetY = offset.y || 20;

  const isFloatingDocked = mode === 'floating' && !isFullscreen;

  // Computed styles
  const containerStyle = getContainerStyle({ isFullscreen, isFloatingDocked, windowWidth, t: themeParams });
  const headerStyle = getHeaderStyle(themeParams);
  const headerTitleStyle = getHeaderTitleStyle(fontFamily);
  const headerSubtitleStyle = getHeaderSubtitleStyle(fontFamily);
  const menuPopupStyle = getMenuPopupStyle(backgroundColor);
  const menuItemStyle = getMenuItemStyle(themeParams);
  const contentCardStyle = getContentCardStyle(backgroundColor);
  const sendButtonStyle = getSendButtonStyle(primaryColor);
  const possibleQueriesContainerStyle = getPossibleQueriesContainerStyle(fontFamily);
  const queryButtonStyle = getQueryButtonStyle(themeParams);
  const confirmOverlayStyle = getConfirmOverlayStyle(showResetConfirm);
  const confirmDialogStyle = getConfirmDialogStyle(themeParams);
  const disclaimerStyle = getDisclaimerStyle(fontFamily);

  const textAreaFontSize = useMemo(() => {
    if (windowWidth <= 768) {
      return Math.max(16, fontSizeNumber) + 'px';
    }
    return fontSize;
  }, [windowWidth, fontSize, fontSizeNumber]);

  const textAreaLineHeight = useMemo(() => {
    const size = windowWidth <= 768 ? Math.max(16, fontSizeNumber) : fontSizeNumber;
    return Math.round(size * 1.5);
  }, [windowWidth, fontSizeNumber]);

  const textAreaMaxHeightCalculated = useMemo(() => {
    return textAreaLineHeight * 3;
  }, [textAreaLineHeight]);

  const textAreaStyle = getTextAreaStyle({
    textAreaFontSize,
    fontFamily,
    textAreaLineHeight,
    textAreaMaxHeightCalculated,
    textColor,
  });

  const hasPendingForm = messages.some((msg, idx) => {
    if (msg.type !== 'form_request' || msg.speaker !== 'agent') return false;
    return !submittedForms.has(idx);
  });

  const pendingForm = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.type === 'form_request' && msg.speaker === 'agent' && !submittedForms.has(i)) {
        try { return { schema: JSON.parse(msg.text), index: i }; }
        catch { /* skip */ }
      }
    }
    return null;
  }, [messages, submittedForms]);

  const isSendDisabled = (inputValue.trim() === '' && attachments.length === 0) || isAgentTyping || hasPendingForm;

  const autoResizeTextArea = () => {
    const el = textAreaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const newHeight = Math.min(el.scrollHeight, textAreaMaxHeightCalculated);
    el.style.height = `${newHeight}px`;
    el.style.overflowY = el.scrollHeight > textAreaMaxHeightCalculated ? 'auto' : 'hidden';
  };

  useEffect(() => {
    autoResizeTextArea();
  }, [inputValue, textAreaMaxHeightCalculated]);

  const showAgentDisclaimer = Boolean(inputDisclaimerHtml);
  const agentDisclaimerContent = showAgentDisclaimer && (
    <span dangerouslySetInnerHTML={{ __html: inputDisclaimerHtml! }} />
  );

  const floatingContainerStyle = getFloatingContainerStyle({
    mode,
    isFullscreen,
    windowWidth,
    windowHeight,
    position,
    offsetX,
    offsetY,
  });

  const renderLanguageSelector = () => {
    if (!SHOW_CHAT_LANGUAGE_SELECTOR) {
      return null;
    }

    if (!hasLanguageOptions || (conversationId && !isFinalized) || messages.length > 0 || hasUserMessages) {
      return null;
    }
    return (
      <LanguageSelector
        availableLanguages={availableLanguages}
        selectedLanguage={resolvedLanguage}
        onLanguageChange={handleLanguageChange}
        translations={translations}
        theme={theme}
      />
    );
  };

  const renderWithReCaptcha = useMemo(() => {
    if (!reCaptchaKey) {
      return (children: React.ReactNode) => <>{children}</>;
    }

    return (children: React.ReactNode) => (
      <GoogleReCaptchaProvider reCaptchaKey={reCaptchaKey || ''}>
        <GoogleReCaptcha
          action="genassist_chat"
          onVerify={handleReCaptchaVerify}
          refreshReCaptcha={false}
        />
        <>{children}</>
      </GoogleReCaptchaProvider>
    );
  }, [reCaptchaKey, handleReCaptchaVerify]);

  const renderChatComponent = () => (
    <div style={containerStyle} data-genassist-root="true">
      <style>{CSS_KEYFRAMES}</style>
      <div style={headerStyle} ref={headerRef}>
        <div style={logoContainerStyle}>
          <img src={logoUrl?.trim() || chatLogo} alt="Logo" style={logoStyle} />
          <div style={headerTitleContainerStyle}>
            <div style={headerTitleStyle}>{headerTitle}</div>
            <div style={headerSubtitleStyle}>
              {description ?? t('header.subtitle')}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            style={menuButtonStyle}
            onClick={handleMenuClick}
            title={t('menu.title')}
          >
            <MoreVertical size={24} color="#111111" />
          </button>
          {mode === 'floating' && (
            <button
              style={menuButtonStyle}
              onClick={() => setIsFloatingOpen(false)}
              title="Close chat"
            >
              <X size={24} color="#111111" />
            </button>
          )}
        </div>
      </div>
      {!noColorAnimation && showBacklight && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: Math.max(0, headerHeight - 14),
            height: 42,
            pointerEvents: 'none',
            zIndex: 1,
            opacity: isAgentTyping ? 1 : 0,
            transition: 'opacity 420ms ease-in-out',
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 6,
              height: 32,
              width: '78%',
              filter: 'blur(22px)',
              background:
                `linear-gradient(90deg, ${hexToRgba(primaryColor, 0.0)} 0%, ${hexToRgba(primaryColor, 0.35)} 15%, ${hexToRgba(primaryColor, 0.55)} 50%, ${hexToRgba(primaryColor, 0.35)} 85%, ${hexToRgba(primaryColor, 0.0)} 100%)`,
              willChange: 'transform, opacity',
              animation: 'ga-backlight-sweep2 1.2s cubic-bezier(0.4,0.0,0.2,1) infinite alternate, ga-backlight-pulse 2.4s ease-in-out infinite',
              borderRadius: 18,
            }}
          />
        </div>
      )}

      {showMenu && (
        <div ref={menuRef} style={menuPopupStyle}>
          <div style={menuItemStyle} onClick={handleResetClick}>
            <RefreshCw size={16} />
            {t('menu.resetConversation')}
          </div>
          {mode !== 'fullscreen' && (
            <div style={menuItemStyle} onClick={handleFullscreenToggle}>
              {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              {t('menu.fullscreen')}
            </div>
          )}
          {hasLanguageOptions && (
            <div
              style={{ ...menuItemStyle, position: 'relative', borderBottom: 'none' }}
              onClick={(e) => {
                e.stopPropagation();
                setShowLanguageDropdown(!showLanguageDropdown);
              }}
            >
              <Globe size={16} />
              <span style={{ flex: 1 }}>{t('menu.language')}</span>
              {showLanguageDropdown && (
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: '100%',
                    marginTop: '4px',
                    backgroundColor: backgroundColor,
                    borderRadius: '8px',
                    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
                    minWidth: '180px',
                    maxWidth: '200px',
                    overflow: 'hidden',
                    zIndex: 1001,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {availableLanguages.map((lang, index) => (
                    <div
                      key={lang.code}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '10px 15px',
                        color: textColor,
                        backgroundColor: resolvedLanguage === lang.code
                          ? (theme?.secondaryColor || '#f5f5f5')
                          : 'transparent',
                        borderBottom: index < availableLanguages.length - 1 ? '1px solid #f0f0f0' : 'none',
                        cursor: 'pointer',
                        fontSize,
                        fontFamily,
                        transition: 'background-color 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (resolvedLanguage !== lang.code) {
                          e.currentTarget.style.backgroundColor = theme?.secondaryColor || '#f5f5f5';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (resolvedLanguage !== lang.code) {
                          e.currentTarget.style.backgroundColor = 'transparent';
                        }
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleLanguageChange(lang.code);
                        setShowLanguageDropdown(false);
                        setShowMenu(false);
                      }}
                    >
                      {lang.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div style={contentCardStyle}>
        <div style={chatContainerStyle} ref={chatContainerRef}>
          {renderLanguageSelector()}

          {(() => {
            const shouldShowSyntheticWelcome =
              showWelcomeBeforeStart &&
              !hasUserMessages &&
              (messages.length === 0 || messages[0].speaker !== 'agent') &&
              (Boolean(welcomeTitle) || Boolean(welcomeImageUrl) || Boolean(welcomeMessage))
              && conversationId;

            if (!shouldShowSyntheticWelcome) return null;

            const now = Math.floor(Date.now() / 1000);
            const syntheticWelcome: ChatMessage = {
              create_time: now,
              start_time: 0,
              end_time: 0.01,
              speaker: 'agent',
              text: welcomeMessage || '',
            };

            return (
              <ChatMessageComponent
                key="__synthetic_welcome__"
                message={syntheticWelcome}
                theme={theme}
                isFirstMessage={true}
                isNextSameSpeaker={false}
                isPrevSameSpeaker={false}
                enableTypewriter={false}
                welcomeImageUrl={welcomeImageUrl || undefined}
                welcomeTitle={welcomeTitle || undefined}
                possibleQueries={possibleQueries}
                onQuickQuery={handleQueryClick}
                onQuickAction={handleQuickAction}
                translations={translations}
                language={resolvedLanguage}
                agentName={agentName}
                isAgentTyping={isAgentTyping}
              />
            );
          })()}
          {(() => {
            const firstAgentIndex = messages.findIndex(m => m.speaker === 'agent');

            const applyMessageFilter = (message: any) => {
              return message.type !== 'file';
            }

            return messages.filter(applyMessageFilter).map((message, index) => {
              if (message.type === 'form_request' && message.speaker === 'agent') {
                try {
                  const formSchema = JSON.parse(message.text);
                  const isPending = !submittedForms.has(index);
                  return (
                    <div key={index} style={{ display: 'flex', flexDirection: 'column', maxWidth: '85%', marginBottom: '8px' }}>
                      <div style={{ fontSize: '14px', color: '#000000', fontWeight: 600, marginBottom: 4 }}>
                        {agentName || 'Agent'}
                      </div>
                      {formDisplay === 'inline' && isPending ? (
                        <DynamicFormMessage
                          schema={formSchema}
                          onSubmit={(data) => handleFormSubmit(data, index)}
                          onCancel={() => handleFormCancel(index)}
                          isSubmitting={submittingFormIndex === index}
                          isSubmitted={false}
                          primaryColor={primaryColor}
                          fontFamily={fontFamily}
                          variant="card"
                        />
                      ) : (
                        <div style={{
                          backgroundColor: '#f3f4f6',
                          borderRadius: '12px',
                          padding: '10px 14px',
                          fontSize: '14px',
                          color: '#374151',
                          fontFamily,
                        }}>
                          {formSchema.message || 'Please fill the form below.'}
                          {isPending && (
                            <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                              Fill the form below to continue.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                } catch {
                  // Fall through to normal rendering if JSON parse fails
                }
              }

              const isNextSameSpeaker = index < messages.length - 1 && messages[index + 1].speaker === message.speaker;
              const isPrevSameSpeaker = index > 0 && messages[index - 1].speaker === message.speaker;
              const isFirstAgentMessage = index === firstAgentIndex && message.speaker === 'agent' && !hasUserMessages;
              const displayMessage =
                isFirstAgentMessage && welcomeMessage
                  ? { ...message, text: welcomeMessage }
                  : message;

              return (
                <ChatMessageComponent
                  key={index}
                  message={displayMessage}
                  theme={theme}
                  onPlayAudio={message.speaker === 'agent' ? playResponseAudio : undefined}
                  isPlayingAudio={isPlayingAudio}
                  isFirstMessage={isFirstAgentMessage}
                  isNextSameSpeaker={isNextSameSpeaker}
                  isPrevSameSpeaker={isPrevSameSpeaker}
                  onFeedback={(messageId, value) => addFeedback(messageId, value)}
                  enableTypewriter={index === messages.length - 1 && message.speaker === 'agent'}
                  welcomeImageUrl={isFirstAgentMessage ? (welcomeImageUrl || undefined) : undefined}
                  welcomeTitle={isFirstAgentMessage ? (welcomeTitle || undefined) : undefined}
                  possibleQueries={isFirstAgentMessage ? possibleQueries : undefined}
                  onQuickQuery={handleQueryClick}
                  onQuickAction={handleQuickAction}
                  onScheduleConfirm={handleScheduleConfirm}
                  isLastMessage={index === messages.length - 1 && message.speaker === 'agent'}
                  translations={translations}
                  language={resolvedLanguage}
                  agentName={agentName}
                  isAgentTyping={isAgentTyping}
                  audioUrlBuilder={message.type === 'audio' && useAudio ? audioUrlBuilder : undefined}
                  audioHeaders={message.type === 'audio' && useAudio ? audioHeaders : undefined}
                  autoPlayAudioMessageId={autoPlayAudioMessageId}
                />
              );
            });
          })()}
          {isAgentTyping && currentThinkingParts.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '80%' }}>
              <div style={{ fontSize: '14px', color: '#000000', fontWeight: 600, marginBottom: 4 }}>{agentName || t('labels.agent')}</div>
              <div style={{
                backgroundColor: 'transparent',
                padding: 0,
                borderRadius: 0,
                maxWidth: '100%',
              }}>
                <div
                  key={`${currentThinkingPartIndex}-${currentThinkingParts.join('|')}`}
                  style={{
                    animation: 'ga-think-change 220ms ease',
                    willChange: 'transform, opacity',
                    color: '#6b7280',
                    fontSize: '13px',
                  }}
                >
                  {currentThinkingParts[currentThinkingPartIndex] || currentThinkingParts[currentThinkingParts.length - 1]}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        {showWelcomeBeforeStart && (() => {
          const showingSyntheticWelcome =
            !hasUserMessages &&
            (messages.length === 0 || messages[0].speaker !== 'agent') &&
            (Boolean(welcomeTitle) || Boolean(welcomeImageUrl) || Boolean(welcomeMessage));
          return (
            possibleQueries.length > 0 &&
            !hasUserMessages &&
            (messages.length === 0 || messages[0].speaker !== 'agent') &&
            !showingSyntheticWelcome
          );
        })() && (
          <div style={possibleQueriesContainerStyle}>
            {possibleQueries.map((query, index) => (
              <button
                key={index}
                style={queryButtonStyle}
                onClick={() => handleQueryClick(query)}
                disabled={isLoading || isAgentTyping}
              >
                {query}
              </button>
            ))}
          </div>
        )}

        {fileErrorToast && (
          <div
            style={{
              margin: '0 16px 8px',
              padding: '10px 14px',
              backgroundColor: '#FFF3E0',
              color: '#E65100',
              borderRadius: '12px',
              fontSize,
              fontFamily,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flexShrink: 0,
            }}
            role="alert"
          >
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{fileErrorToast}</span>
          </div>
        )}

        {useFile && attachments.length > 0 && (
          <div style={{ padding: '0 16px', marginBottom: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {attachments.map((att, index) => (
              <AttachmentPreview
                key={index}
                file={att.file}
                onRemove={() => handleRemoveAttachment(att.file.name)}
                uploading={uploadingFiles.has(att.file.name)}
              />
            ))}
          </div>
        )}

        {!conversationId || isFinalized ? (
          <div style={inputContainerStyle}>
            <button
              type="button"
              style={{...sendButtonStyle, width: '100%', height: '48px', borderRadius: '16px', cursor: 'pointer', fontFamily, fontSize}}
              onClick={handleStartConversation}
              disabled={isLoading}
            >
              {t('buttons.startConversation')}
            </button>
          </div>
        ) : pendingForm && formDisplay === 'footer' ? (
          <div style={{
            ...inputContainerStyle,
            flexDirection: 'column',
            borderTop: '1px solid #e5e7eb',
          }}>
            <DynamicFormMessage
              schema={pendingForm.schema}
              onSubmit={(data) => handleFormSubmit(data, pendingForm.index)}
              onCancel={() => handleFormCancel(pendingForm.index)}
              isSubmitting={submittingFormIndex === pendingForm.index}
              isSubmitted={false}
              primaryColor={primaryColor}
              fontFamily={fontFamily}
              variant="footer"
            />
            {agentDisclaimerContent && (
              <div className="ga-input-disclaimer" style={disclaimerStyle}>
                {agentDisclaimerContent}
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={inputContainerStyle}>
            <div style={{ display: 'flex', flexDirection: 'column', width: '100%', minWidth: 0 }}>
            <div style={inputWrapperStyle}>
              {useFile && (
                <>
                  <button
                    type="button"
                    style={attachButtonStyle}
                    title="Attach"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Paperclip size={22} color="#757575" />
                  </button>
                  <input
                    type="file"
                    multiple
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    onChange={handleFileChange}
                    accept={allowedExtensions.join(',') || '*/*'}
                  />
                </>
              )}
              <textarea
                ref={textAreaRef}
                style={textAreaStyle}
                className="ga-textarea-nosb"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if ((inputValue.trim() !== '' || attachments.length > 0) && !isAgentTyping && !hasPendingForm) {
                      submitMessage();
                    }
                  }
                }}
                placeholder={inputPlaceholder}
                disabled={!conversationId || isFinalized || hasPendingForm}
                rows={1}
              />
              <div style={rightActionContainerStyle}>
                {!(useAudio && inputValue.trim() === '' && attachments.length === 0) && (
                  <button
                    type="submit"
                    style={{ ...sendButtonStyle, ...(isSendDisabled ? sendButtonDisabledStyle : {}) }}
                    disabled={isSendDisabled}
                  >
                    <ArrowUp size={18} strokeWidth={3} color="#ffffff" />
                  </button>
                )}
              </div>
              {useAudio && inputValue.trim() === '' && attachments.length === 0 && (
                <VoiceInput
                  onAudioReady={async (blob: Blob, format: string) => {
                    try {
                      setIsPlayingAudio(true);
                      await sendAudioMessage(blob, format);
                    } catch {
                      // error handled inside sendAudioMessage
                    } finally {
                      setIsPlayingAudio(false);
                    }
                  }}
                  onError={handleVoiceError}
                  theme={theme}
                />
              )}
            </div>

            {agentDisclaimerContent && (
              <div className="ga-input-disclaimer" style={disclaimerStyle}>
                {agentDisclaimerContent}
              </div>
            )}
            </div>
          </form>
        )}
      </div>

      <div style={confirmOverlayStyle}>
        <div style={confirmDialogStyle}>
          <h3 style={{fontFamily, marginTop: 0}}>{t('dialog.resetConversation.title')}</h3>
          <p style={{fontFamily, fontSize}}>{t('dialog.resetConversation.message')}</p>
          <div style={confirmButtonsStyle}>
            <button style={{...getConfirmButtonStyle(false, themeParams), color: textColor}} onClick={handleCancelReset}>{t('buttons.cancel')}</button>
            <button style={getConfirmButtonStyle(true, themeParams)} onClick={handleConfirmReset}>{t('buttons.reset')}</button>
          </div>
        </div>
      </div>
    </div>
  );

  if (mode === 'floating') {
    return (
      <>
        {!isFloatingOpen && (
          <ChatBubble
            showChat={isFloatingOpen}
            onClick={() => setIsFloatingOpen(prev => !prev)}
            primaryColor={primaryColor}
            style={getPositionStyles({ position, offsetX, offsetY })}
            chatBubbleIcon={theme?.chatBubbleIcon}
          />
        )}

        {isFloatingOpen && (
          <div style={floatingContainerStyle} data-genassist-container="floating">
            {renderWithReCaptcha(renderChatComponent())}
          </div>
        )}
      </>
    );
  }

  if (mode === 'fullscreen') {
    return (
      <div style={floatingContainerStyle} data-genassist-container="fullscreen">
        {renderWithReCaptcha(renderChatComponent())}
      </div>
    );
  }

  return renderWithReCaptcha(renderChatComponent());
};
