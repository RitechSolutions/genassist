import React, { useState, useRef, useEffect, useLayoutEffect, useMemo, useCallback } from 'react';
import { ChatMessageComponent } from './ChatMessage';
import { AttachmentPreview } from './common/AttachmentPreview';
import { useChat } from '../hooks/useChat';
import { ChatMessage, GenAgentChatProps, ScheduleItem, Attachment, AttachmentWithFile } from '../types';
import { VoiceInput } from './VoiceInput';
import { AudioService } from '../services/audioService';
import { Paperclip, MoreVertical, RefreshCw, Globe, X, ArrowUp, Maximize2, Minimize2 } from 'lucide-react';
import { ChatBubble } from './ChatBubble';
import { LanguageSelector } from './LanguageSelector';
import chatLogo from '../assets/chat-logo.png';

// Type for attachment with file reference

import {
  resolveLanguage,
  mergeTranslations,
  getTranslationString,
  getTranslationArray,
  getTranslationsForLanguage,
} from '../utils/i18n';
import { GoogleReCaptcha, GoogleReCaptchaProvider } from 'react-google-recaptcha-v3';


export const GenAgentChat: React.FC<GenAgentChatProps> = ({
  baseUrl,
  apiKey,
  tenant,
  metadata,
  useWs = true,
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
    // First get base translations for the language
    const baseTranslations = getTranslationsForLanguage(resolvedLanguage);
    // Then merge with any custom translations provided
    return mergeTranslations(customTranslations, baseTranslations);
  }, [resolvedLanguage, customTranslations]);

  // Translation helper function
  const t = (key: string, fallback?: string): string => {
    return getTranslationString(key, translations, fallback);
  };

  // Get translated placeholder or use provided/default
  // Make it reactive to language changes
  const inputPlaceholder = useMemo(() => {
    // If placeholder prop is explicitly provided, use it
    // Otherwise, use the translation which will update with language changes
    return placeholder || t('input.placeholder', 'Ask a question');
  }, [placeholder, translations]);
  const [inputValue, setInputValue] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showLanguageDropdown, setShowLanguageDropdown] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [isFloatingOpen, setIsFloatingOpen] = useState(false);
  const [attachments, setAttachments] = useState<AttachmentWithFile[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<Set<string>>(new Set());
  const menuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const [headerHeight, setHeaderHeight] = useState(56);
  const [showBacklight, setShowBacklight] = useState(false);
  const [isFullscreenToggled, setIsFullscreenToggled] = useState(false);

  // default thinking messages if none provided by workflow
  const DEFAULT_THINKING_MESSAGES = useMemo(
    () => getTranslationArray('thinking.messages', translations, [
      "Thinking…",
      "Analyzing your question…",
      "Searching knowledge…",
      "Pulling relevant info…",
      "Drafting the answer…",
      "Double‑checking details…",
      "Tying it together…",
      "Almost there…",
    ]),
    [translations]
  );
  const [currentThinkingParts, setCurrentThinkingParts] = useState<string[]>([]);
  const [currentThinkingPartIndex, setCurrentThinkingPartIndex] = useState(0);
  const {
    messages,
    isLoading,
    sendMessage,
    uploadFile,
    resetConversation,
    startConversation,
    connectionState,
    conversationId,
    possibleQueries,
    isFinalized,
    isAgentTyping,
    addFeedback,
    welcomeTitle,
    welcomeImageUrl,
    welcomeMessage,
    thinkingPhrases,
    thinkingDelayMs,
  } = useChat({
    baseUrl,
    apiKey,
    tenant,
    metadata: metadataWithLanguage,
    useWs,
    language: resolvedLanguage,
    onError,
    onTakeover,
    onFinalize
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioService = useRef<AudioService | null>(null);
  const hasAnchoredHistory = useRef(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const reCaptchaTokenRef = useRef<string | undefined>(undefined);
  const isUserAtBottomRef = useRef(true);

  const anchorHistory = () => {
    const el = chatContainerRef.current;
    if (!el || !messages.length || hasAnchoredHistory.current) return;
    if (el.clientHeight === 0) return; // hidden, wait for visibility/size
    el.scrollTop = el.scrollHeight;
    hasAnchoredHistory.current = true;
    isUserAtBottomRef.current = true;
  };

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth', force: boolean = false) => {
    const container = chatContainerRef.current;
    const el = messagesEndRef.current;
    if (!container || !el) return;
    
    // Only scroll if user is at bottom or if forced (e.g., for agent typing)
    if (!force && !isUserAtBottomRef.current) {
      return;
    }
    
    const doScroll = () => {
      container.scrollTo({ top: container.scrollHeight, behavior });
      isUserAtBottomRef.current = true;
    };
    if (behavior === 'auto') {
      doScroll();
    } else {
      requestAnimationFrame(doScroll);
    }
  };

  const hasUserMessages = messages.some(message => message.speaker === 'customer');

  useEffect(() => {
    audioService.current = new AudioService({ baseUrl, apiKey });
  }, [baseUrl, apiKey]);

  useLayoutEffect(() => {
    if (!messages.length) return;
    if (hasAnchoredHistory.current) {
      scrollToBottom('smooth', false);
    } else {
      anchorHistory();
    }
  }, [messages]);

  useLayoutEffect(() => {
    if (!isAgentTyping) return;
    // Force scroll when agent is typing
    scrollToBottom('auto', true);
  }, [isAgentTyping, currentThinkingPartIndex, currentThinkingParts.length]);

  useEffect(() => {
    hasAnchoredHistory.current = false;
  }, [conversationId]);

  // Ensure chat is always open when mode is fullscreen
  useEffect(() => {
    if (mode === 'fullscreen' && !isFloatingOpen) {
      setIsFloatingOpen(true);
    }
  }, [mode, isFloatingOpen]);

  // Scroll to bottom when chat is reopened in floating mode
  const prevIsFloatingOpenRef = useRef(isFloatingOpen);
  useEffect(() => {
    // Only trigger when chat transitions from closed to open
    if ((mode === 'floating' || mode === 'fullscreen') && isFloatingOpen && !prevIsFloatingOpenRef.current && messages.length > 0) {
      // Reset the anchor flag so it can scroll to bottom
      hasAnchoredHistory.current = false;
      isUserAtBottomRef.current = true;
      
      // Wait for container to be visible and then scroll
      const scrollWhenVisible = () => {
        const container = chatContainerRef.current;
        if (!container) {
          requestAnimationFrame(scrollWhenVisible);
          return;
        }
        
        // Check if container is visible
        if (container.clientHeight === 0) {
          requestAnimationFrame(scrollWhenVisible);
          return;
        }
        
        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
        hasAnchoredHistory.current = true;
        isUserAtBottomRef.current = true;
      };
      
      // Use requestAnimationFrame to wait for render
      requestAnimationFrame(() => {
        requestAnimationFrame(scrollWhenVisible);
      });
    }
    prevIsFloatingOpenRef.current = isFloatingOpen;
  }, [isFloatingOpen, mode]);

  useEffect(() => {
    if (!messages.length) return;
    const el = chatContainerRef.current;
    if (!el) return;

    // Observe size/visibility changes to anchor chat view.
    const resizeObserver = new ResizeObserver(() => {
      if (isUserAtBottomRef.current) {
        anchorHistory();
      }
    });
    resizeObserver.observe(el);

    anchorHistory();

    return () => {
      resizeObserver.disconnect();
    };
  }, [messages]);

  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;

    const isAtBottom = (threshold: number = 100): boolean => {
      if (!container) return true;
      const { scrollTop, scrollHeight, clientHeight } = container;
      return scrollHeight - scrollTop - clientHeight <= threshold;
    };
    const handleScroll = () => {
      isUserAtBottomRef.current = isAtBottom();
    };
    container.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => {
      container.removeEventListener('scroll', handleScroll);
    };
  }, []);

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

  // Smoothly show/hide the backlight while the agent is typing
  useEffect(() => {
    if (isAgentTyping) {
      setShowBacklight(true);
      return;
    }
    const t = setTimeout(() => setShowBacklight(false), 420); // allow fade-out
    return () => clearTimeout(t);
  }, [isAgentTyping]);

  // Show "thinking" phrases while agent is typing
  useEffect(() => {
    if (!isAgentTyping) {
      setCurrentThinkingParts([]);
      setCurrentThinkingPartIndex(0);
      return;
    }

    // Randomly select a phrase from the list
    const list = (thinkingPhrases && thinkingPhrases.length > 0) ? thinkingPhrases : DEFAULT_THINKING_MESSAGES;
    const randomIndex = Math.floor(Math.random() * list.length);
    const selectedPhrase = list[randomIndex];

    // Split by | to get parts, or use the phrase as a single part if no | found
    const parts = selectedPhrase.includes('|') 
      ? selectedPhrase.split('|').map(part => part.trim()).filter(part => part.length > 0)
      : [selectedPhrase.trim()];

    // Initialize with first part
    setCurrentThinkingParts(parts);
    setCurrentThinkingPartIndex(0);

    // If there's only one part, no need to progress
    if (parts.length <= 1) return;

    // Progress through parts with delay, but stop at the last one
    const rotDelay = Math.max(250, thinkingDelayMs || 1000);
    const timeoutIds: ReturnType<typeof setTimeout>[] = [];

    // Set up timeouts for each part transition
    for (let i = 1; i < parts.length; i++) {
      const timeoutId = setTimeout(() => {
        setCurrentThinkingPartIndex(i);
      }, rotDelay * i);
      timeoutIds.push(timeoutId);
    }

    return () => {
      timeoutIds.forEach(id => clearTimeout(id));
    };
  }, [isAgentTyping, thinkingPhrases, thinkingDelayMs]);

  const submitMessage = async () => {
    if (inputValue.trim() === '' && attachments.length === 0) return;
    if (isAgentTyping) return; // Prevent sending while agent is thinking/typing
    const textToSend = inputValue;
    // NOTES: we don't upload files anymore, we just send the content blocks
    const filesToUpload = attachments.map(a => a.file);
    // const fileAttachments = attachments.map(a => a.attachment);

    setInputValue('');
    setAttachments([]);
    // Reset the file input value so the same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    try {
      // Include FAQ query in metadata if one was previously selected
      const extraMetadata: Record<string, any> = {};

      if (selectedFaqQuery) {
        extraMetadata.faq_query = selectedFaqQuery;
      }

      if (filesToUpload.length > 0) {
        extraMetadata.attachments = attachments.map(a => a.attachment);
      }
      
      // send message with attachments
      await sendMessage(textToSend, filesToUpload, extraMetadata, reCaptchaTokenRef.current);
    } catch (error) {
      // ignore
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitMessage();
  };

  const handleQuickAction = async (text: string) => {
    if (!text.trim()) return;
    if (isAgentTyping) return; // Prevent sending while agent is thinking/typing
    try {
      // Include FAQ query in metadata if one was previously selected
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

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      
      // Initialize attachments with files (attachment reference will be null initially)
      const newAttachments: AttachmentWithFile[] = newFiles.map(file => ({file, attachment: null}));
      setAttachments(prev => [...prev, ...newAttachments]);

      const newUploadingFiles = new Set(uploadingFiles);
      newFiles.forEach(file => newUploadingFiles.add(file.name));
      setUploadingFiles(newUploadingFiles);

      try {
        // Upload files and get attachment references
        const uploadResults = await Promise.all(
          newFiles.map(async (file, index) => ({
            file,
            index,
            attachment: await uploadFile(file),
          }))
        );

        // Create a map of file reference (name + size + lastModified) to uploaded attachment
        const fileToAttachmentMap = new Map<string, Attachment | null>();
        uploadResults.forEach(({ file, attachment }) => {
          const fileKey = `${file.name}:${file.size}:${file.lastModified}`;
          fileToAttachmentMap.set(fileKey, attachment);
        });

        // Update attachments with the uploaded file references
        setAttachments(prev => {
          return prev.map(att => {
            const fileKey = `${att.file.name}:${att.file.size}:${att.file.lastModified}`;
            const uploadedAttachment = fileToAttachmentMap.get(fileKey);
            
            // If this attachment matches one of the newly uploaded files, update it
            if (uploadedAttachment !== undefined) {
              return {
                ...att,
                attachment: uploadedAttachment,
              };
            }
            return att;
          });
        });
      } catch (error) {
        // ignore
        console.error('Error uploading file', error);
      } finally {
        const finalUploadingFiles = new Set(uploadingFiles);
        newFiles.forEach(file => finalUploadingFiles.delete(file.name));
        setUploadingFiles(finalUploadingFiles);
        // Reset the file input value so the same file can be selected again
        if (fileInputRef.current) {
          fileInputRef.current!.value = '';
        }
      }
    }
  };

  const handleRemoveAttachment = (fileName: string) => {
    setAttachments(prev => prev.filter(att => att.file.name !== fileName));
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

  const handleQueryClick = async (query: string) => {
    if (isAgentTyping || isLoading) return; // Prevent sending while agent is thinking/typing
    
    // Store the FAQ query for all subsequent messages
    setSelectedFaqQuery(query);
    
    try {
      await sendMessage(query, [], { faq_query: query }, reCaptchaTokenRef.current);
    } catch (error) {
      // ignore
    }
  };

  const handleStartConversation = async () => {
    if (isLoading) return;

    // Clear input text and file attachments when starting a conversation
    setInputValue('');
    setAttachments([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

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
    // Clear input text and file attachments when restarting
    setInputValue('');
    setAttachments([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    await resetConversation(reCaptchaTokenRef.current);
    setSelectedFaqQuery(null); // Clear FAQ query on reset
    setShowResetConfirm(false);
  };

  const handleCancelReset = () => {
    setShowResetConfirm(false);
  };

  const handleLanguageChange = (lang: string) => {
    setSelectedLanguage(lang);
  };

  const handleFullscreenToggle = () => {
    setIsFullscreenToggled(prev => !prev);
    setShowMenu(false);
  };

  // Track window resize to update mobile detection
  const [windowWidth, setWindowWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1024);
  
  // Automatically determine if should be fullscreen (mobile devices or widget mode or manual toggle or fullscreen mode)
  const isFullscreen = useMemo(() => {
    // If mode is fullscreen, always fullscreen
    if (mode === 'fullscreen') return true;
    // If widget prop is true, always fullscreen
    if (widget) return true;
    // If manually toggled, use toggle state
    if (isFullscreenToggled) return true;
    // Otherwise, use mobile detection
    return windowWidth <= 768;
  }, [windowWidth, widget, isFullscreenToggled, mode]);

  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Lock body scroll when fullscreen is active on mobile
  useEffect(() => {
    if (isFullscreen && typeof document !== 'undefined') {
      const originalStyle = window.getComputedStyle(document.body).overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalStyle;
      };
    }
  }, [isFullscreen]);

  const handleReCaptchaVerify = useCallback((token: string) => {
    reCaptchaTokenRef.current = token;
  }, []);

  // Available languages (can be extended)
  const availableLanguages = [
    { code: 'en', name: 'English' },
    { code: 'es', name: 'Español' },
    { code: 'fr', name: 'Français' },
    { code: 'de', name: 'Deutsch' },
    { code: 'it', name: 'Italiano' },
    { code: 'pt', name: 'Português' },
  ];

  const primaryColor = theme?.primaryColor || '#2962FF';
  const backgroundColor = theme?.backgroundColor || '#ffffff';
  const textColor = theme?.textColor || '#000000';
  const fontFamily = theme?.fontFamily || 'Roboto, Arial, sans-serif';
  const fontSize = theme?.fontSize || '14px';
  const fontSizeNumber = typeof fontSize === 'string' ? parseInt(fontSize, 10) : (typeof fontSize === 'number' ? fontSize : 14);
  const lineHeightPx = Math.round(fontSizeNumber * 1.5);
  const textAreaMaxHeight = lineHeightPx * 3; // up to 3 lines

  // Helper function to convert hex color to rgba
  const hexToRgba = (hex: string, alpha: number): string => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const position = floatingConfig.position || 'bottom-right';
  const offset = floatingConfig.offset || { x: 20, y: 20 };
  const offsetX = offset.x || 20;
  const offsetY = offset.y || 20;

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    // When fullscreen, let height be calculated from top/bottom, otherwise use specified height
    height: isFullscreen ? undefined : '100%',
    maxHeight: isFullscreen ? undefined : (windowWidth > 768 ? '700px' : '600px'),
    width: isFullscreen ? '100vw' : '100%',
    maxWidth: isFullscreen ? '100vw' : '400px',
    border: isFullscreen ? 'none' : '1px solid #e0e0e0',
    borderRadius: isFullscreen ? '0' : '32px',
    overflow: 'hidden',
    backgroundColor: theme?.secondaryColor || '#f5f5f5',
    fontFamily,
    boxShadow: isFullscreen ? 'none' : "0 4px 20px rgba(0, 0, 0, 0.2)",
    position: isFullscreen ? 'fixed' : 'relative',
    top: isFullscreen ? 0 : undefined,
    left: isFullscreen ? 0 : undefined,
    right: isFullscreen ? 0 : undefined,
    // Position container above browser footer using safe area insets
    bottom: isFullscreen ? 'env(safe-area-inset-bottom, 0px)' : undefined,
    zIndex: isFullscreen ? 9999 : undefined,
  };

  const headerStyle: React.CSSProperties = {
    padding: '15px',
    backgroundColor: theme?.secondaryColor || '#f5f5f5',
    color: '#111111',
    fontWeight: 'bold',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    position: 'relative',
  };

  const logoContainerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    position: 'relative',
    zIndex: 1,
  };

  const logoStyle: React.CSSProperties = {
    width: '28px',
    height: '28px',
  };

  const headerTitleContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
  };

  const headerTitleStyle: React.CSSProperties = {
    fontSize: '16px',
    fontWeight: 'bold',
    margin: 0,
    fontFamily,
  };

  const headerSubtitleStyle: React.CSSProperties = {
    fontSize: '14px',
    fontWeight: 'normal',
    margin: 0,
    fontFamily,
  };

  const menuButtonStyle: React.CSSProperties = {
    backgroundColor: 'transparent',
    color: '#111111',
    border: 'none',
    borderRadius: '50%',
    width: '32px',
    height: '32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    outline: 'none',
    position: 'relative',
    zIndex: 1,
  };

  const menuPopupStyle: React.CSSProperties = {
    position: 'absolute',
    top: '50px',
    right: '15px',
    backgroundColor: backgroundColor,
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    zIndex: 1000,
    minWidth: '150px',
    overflow: 'visible',
  };

  const menuItemStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 15px',
    color: textColor,
    cursor: 'pointer',
    fontSize,
    fontFamily,
    borderBottom: '1px solid #f0f0f0',
  };


  const chatContainerStyle: React.CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: '15px',
    backgroundColor: 'transparent',
    display: 'flex',
    flexDirection: 'column',
  };

  const inputContainerStyle: React.CSSProperties = {
    display: 'flex',
    padding: '12px 15px',
    backgroundColor: '#ffffff',
    alignItems: 'center',
    gap: '8px',
    flexShrink: 0,
    overflowX: 'hidden',
    minWidth: 0,
  };

  const inputWrapperStyle: React.CSSProperties = {
    display: 'flex',
    flex: 1,
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: '24px',
    border: '1px solid #e5e7eb',
    padding: '0 12px',
    minHeight: '50px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.06)',
    position: 'relative',
    overflowX: 'hidden',
    minWidth: 0,
  };

  // Use at least 16px font size on mobile to prevent zoom
  const textAreaFontSize = useMemo(() => {
    if (windowWidth <= 768) {
      // On mobile, use at least 16px to prevent zoom
      return Math.max(16, fontSizeNumber) + 'px';
    }
    return fontSize;
  }, [windowWidth, fontSize, fontSizeNumber]);

  const textAreaLineHeight = useMemo(() => {
    const size = windowWidth <= 768 ? Math.max(16, fontSizeNumber) : fontSizeNumber;
    return Math.round(size * 1.5);
  }, [windowWidth, fontSizeNumber]);

  const textAreaMaxHeightCalculated = useMemo(() => {
    return textAreaLineHeight * 3; // up to 3 lines
  }, [textAreaLineHeight]);

  const textAreaStyle: React.CSSProperties = {
    flex: 1,
    border: 'none',
    outline: 'none',
    background: 'transparent',
    fontSize: textAreaFontSize,
    fontFamily,
    padding: '10px',
    paddingRight: '46px',
    color: textColor,
    resize: 'none',
    lineHeight: `${textAreaLineHeight}px`,
    maxHeight: `${textAreaMaxHeightCalculated}px`,
    overflowY: 'hidden',
    overflowX: 'hidden',
    minWidth: 0,
    width: '100%',
    boxSizing: 'border-box',
  };

  const attachButtonStyle: React.CSSProperties = {
    backgroundColor: 'transparent',
    border: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    outline: 'none',
    color: '#757575',
    padding: 0,
  };

  const sendButtonStyle: React.CSSProperties = {
    backgroundColor: primaryColor,
    color: '#ffffff',
    border: 'none',
    borderRadius: '50%',
    width: '36px',
    height: '36px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    outline: 'none',
    flexShrink: 0,
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
  };

  const rightActionContainerStyle: React.CSSProperties = {
    position: 'absolute',
    right: '4px',
    top: '50%',
    transform: 'translateY(-50%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

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

  const possibleQueriesContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '0',
    paddingLeft: '28px',
    paddingRight: '28px',
    marginTop: '5px',
    marginBottom: '15px',
    width: '100%',
    fontFamily,
  };

  const queryButtonStyle: React.CSSProperties = {
    padding: '12px 15px',
    backgroundColor: theme?.secondaryColor || '#f5f5f5',
    color: textColor,
    border: 'none',
    borderRadius: '6px',
    fontSize,
    cursor: 'pointer',
    textAlign: 'left',
    fontWeight: 'normal',
    boxShadow: 'none',
    width: '100%',
    maxWidth: '240px',
    fontFamily,
  };

  const confirmOverlayStyle: React.CSSProperties = {
    display: showResetConfirm ? 'flex' : 'none',
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    zIndex: 10,
    justifyContent: 'center',
    alignItems: 'center',
  };

  const confirmDialogStyle: React.CSSProperties = {
    backgroundColor: backgroundColor,
    padding: '20px',
    borderRadius: '8px',
    maxWidth: '300px',
    textAlign: 'center',
    fontFamily,
    color: textColor,
  };

  const confirmButtonsStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'center',
    marginTop: '15px',
    gap: '10px',
  };

  const confirmButtonStyle = (isConfirm: boolean): React.CSSProperties => ({
    padding: '8px 16px',
    backgroundColor: isConfirm ? '#F44336' : '#e0e0e0',
    color: isConfirm ? '#ffffff' : textColor,
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontFamily,
    fontSize,
  });

  const contentCardStyle: React.CSSProperties = {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    boxShadow: '0 -2px 6px rgba(0,0,0,0.03)',
    position: 'relative',
    zIndex: 2,
    overflow: 'hidden',
    minHeight: 0,
  };

  // Floating mode styles
  const getPositionStyles = (): React.CSSProperties => {
    const base: React.CSSProperties = {
      position: 'fixed',
      zIndex: 1000,
    };

    switch (position) {
      case 'bottom-right':
        return { ...base, bottom: offsetY, right: offsetX };
      case 'bottom-left':
        return { ...base, bottom: offsetY, left: offsetX };
      case 'top-right':
        return { ...base, top: offsetY, right: offsetX };
      case 'top-left':
        return { ...base, top: offsetY, left: offsetX };
      default:
        return { ...base, bottom: offsetY, right: offsetX };
    }
  };

  const getChatPositionStyles = (): React.CSSProperties => {
    const base: React.CSSProperties = {
      position: 'fixed',
      borderRadius: '32px',
      zIndex: 999,
    };

    switch (position) {
      case 'bottom-right':
        return { 
          ...base, 
          bottom: offsetY,
          right: offsetX 
        };
      case 'bottom-left':
        return { 
          ...base, 
          bottom: offsetY,
          left: offsetX 
        };
      case 'top-right':
        return { 
          ...base, 
          top: offsetY,
          right: offsetX 
        };
      case 'top-left':
        return { 
          ...base, 
          top: offsetY,
          left: offsetX 
        };
      default:
        return { 
          ...base, 
          bottom: offsetY,
          right: offsetX 
        };
    }
  };

  const getResponsiveDimensions = () => {
    const screenWidth = typeof window !== 'undefined' ? window.innerWidth : 1024;
    // If fullscreen on mobile, use full viewport
    if (isFullscreen) {
      return { width: '100vw', height: '100vh', borderRadius: '0' };
    }
    if (screenWidth <= 480) {
      return { width: 'calc(100vw - 40px)', height: '450px' };
    } else if (screenWidth <= 768) {
      return { width: '350px', height: '500px' };
    } else {
      return { width: '380px', height: '700px' };
    }
  };

  const floatingContainerStyle: React.CSSProperties = {
    ...((mode === 'fullscreen' || (isFullscreen && windowWidth <= 768))
      ? { 
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 'env(safe-area-inset-bottom, 0px)',
          width: '100vw',
          // Height will be automatically calculated from top and bottom
          borderRadius: '0',
          zIndex: 9999,
        }
      : {
          ...getChatPositionStyles(),
          ...getResponsiveDimensions(),
        }
    ),
  };

  /**
   * Render the component with ReCaptcha
   * @param children - The children to be rendered
   * @returns The rendered component
   */
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
      <style>{`
        @keyframes blink { 0% { opacity: 0.2; } 20% { opacity: 1; } 100% { opacity: 0.2; } }
        /* Hide scrollbars for the expanding textarea but keep scrolling */
        .ga-textarea-nosb { 
          scrollbar-width: none; 
          -ms-overflow-style: none; 
          max-width: 100%;
          box-sizing: border-box;
        }
        .ga-textarea-nosb::-webkit-scrollbar { width: 0; height: 0; }
        /* Prevent zoom on mobile - ensure minimum 16px font size */
        @media (max-width: 768px) {
          .ga-textarea-nosb {
            font-size: 16px !important;
          }
        }
        /* Backlight sweep under content edge (GPU-friendly).
           Wider travel to fully reach both corners. */
        @keyframes ga-backlight-sweep2 { 0% { transform: translateX(-35%); } 100% { transform: translateX(105%); } }
        @keyframes ga-backlight-pulse { 0%,100% { opacity: 0.7; } 50% { opacity: 1; } }
        @keyframes ga-think-change { 0% { opacity: 0; transform: translateY(4px); } 100% { opacity: 1; transform: translateY(0); } }
        /* Hide reCAPTCHA badge */
        /* Ensure reCAPTCHA container is always hidden */
        .grecaptcha-badge {
          display: none !important;
          visibility: hidden !important;
          position: absolute !important;
          width: 0 !important;
          height: 0 !important;
          overflow: hidden !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }
        /* Support for safe area insets - handled via inline styles on input container */
      `}</style>
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
        </div>
      )}
      
      <div style={contentCardStyle}>
        <div style={chatContainerStyle} ref={chatContainerRef}>
          {/* Language Selector - Show only when no conversation started */}
          {(!conversationId || isFinalized) && messages.length === 0 && !hasUserMessages && (
            <LanguageSelector
              availableLanguages={availableLanguages}
              selectedLanguage={resolvedLanguage}
              onLanguageChange={handleLanguageChange}
              translations={translations}
              theme={theme}
            />
          )}
          {(() => {
            return null;
          })()}
          {(() => {
            // show welcome card (only when showWelcomeBeforeStart is true)
            const shouldShowSyntheticWelcome =
              showWelcomeBeforeStart &&
              !hasUserMessages &&
              (messages.length === 0 || messages[0].speaker !== 'agent') &&
              (Boolean(welcomeTitle) || Boolean(welcomeImageUrl) || Boolean(welcomeMessage));

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
              // filter out file messages added by the agent
              return message.type !== 'file';
            }

            return messages.filter(applyMessageFilter).map((message, index) => {
              const isNextSameSpeaker = index < messages.length - 1 && messages[index + 1].speaker === message.speaker;
              const isPrevSameSpeaker = index > 0 && messages[index - 1].speaker === message.speaker;
              const isFirstAgentMessage = index === firstAgentIndex && message.speaker === 'agent' && !hasUserMessages;

              return (
                <ChatMessageComponent 
                  key={index} 
                  message={message} 
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
        ) : (
          <form onSubmit={handleSubmit} style={inputContainerStyle}>
            <div style={inputWrapperStyle}>
              {useFile && (
                <>
                  <button 
                    type="button" 
                    style={attachButtonStyle}
                    title="Attach"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isAgentTyping}
                  >
                    <Paperclip size={22} color={isAgentTyping ? "#b0b0b0" : "#757575"} />
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
                    if ((inputValue.trim() !== '' || attachments.length > 0) && connectionState === 'connected' && !isAgentTyping) {
                      submitMessage();
                    }
                  }
                }}
                placeholder={inputPlaceholder}
                disabled={!conversationId || isFinalized || isAgentTyping}
                rows={1}
              />
              <div style={rightActionContainerStyle}>
                {useAudio && inputValue.trim() === '' && attachments.length === 0 ? (
                  <VoiceInput
                    onTranscription={(text: string) => setInputValue(text)}
                    onError={handleVoiceError}
                    baseUrl={baseUrl}
                    apiKey={apiKey}
                    theme={theme}
                    disabled={isAgentTyping}
                  />
                ) : (
                  <button 
                    type="submit" 
                    style={sendButtonStyle}
                    disabled={(inputValue.trim() === '' && attachments.length === 0) || connectionState !== 'connected' || isAgentTyping}
                  >
                    <ArrowUp size={18} strokeWidth={3} color="#ffffff" />
                  </button>
                )}
              </div>
            </div>
          </form>
        )}
      </div>

      <div style={confirmOverlayStyle}>
        <div style={confirmDialogStyle}>
          <h3 style={{fontFamily, marginTop: 0}}>{t('dialog.resetConversation.title')}</h3>
          <p style={{fontFamily, fontSize}}>{t('dialog.resetConversation.message')}</p>
          <div style={confirmButtonsStyle}>
            <button style={{...confirmButtonStyle(false), color: textColor}} onClick={handleCancelReset}>{t('buttons.cancel')}</button>
            <button style={confirmButtonStyle(true)} onClick={handleConfirmReset}>{t('buttons.reset')}</button>
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
            style={getPositionStyles()}
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
