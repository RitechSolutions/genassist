import React, { useState, useRef, useEffect, useLayoutEffect, useMemo, useCallback } from 'react';
import { ChatMessageComponent } from './ChatMessage';
import { AttachmentPreview } from './common/AttachmentPreview';
import { useChat } from '../hooks/useChat';
import { useReadReporter, messageIdentityKey } from '../hooks/useReadReporter';
import { useScrollManagement } from '../hooks/useScrollManagement';
import { useThinkingAnimation } from '../hooks/useThinkingAnimation';
import { useViewportManager } from '../hooks/useViewportManager';
import { useFileAttachments } from '../hooks/useFileAttachments';
import { ChatMessage, GenAgentChatProps, ScheduleItem } from '../types';
import { VoiceInput } from './VoiceInput';
import { LiveCallControl } from './LiveCallControl';
import { useLiveVoice as useLiveVoiceSession } from '../hooks/useLiveVoice';
import { AudioService } from '../services/audioService';
import { Paperclip, MoreHorizontal, RefreshCw, Globe, X, ArrowUp, ArrowDown, Maximize2, Minimize2, AlertCircle, Fullscreen, ChevronDown } from 'lucide-react';
import { BubbleDock } from './BubbleDock';
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
  headerLeftContainerStyle,
  headerRightContainerStyle,
  headerPillStyle,
  logoStyle,
  brandLogoStyle,
  getHeaderPillTitleStyle,
  headerPillTextColumnStyle,
  getHeaderDescriptionTextStyle,
  menuButtonStyle,
  getMenuPopupStyle,
  getMenuItemStyle,
  chatContainerStyle,
  getInputContainerStyle,
  getInputWrapperStyle,
  getTextAreaStyle,
  getLiveVoiceHintStyle,
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
  getFloatingContainerStyle,
  getInputBarRootStyle,
  getInputBarBarStyle,
  getInputBarFaqListStyle,
  getInputBarFaqChipStyle,
  getInputBarReplyCardStyle,
  getInputBarPanelStyle,
  getInputBarPanelHeaderStyle,
  getScrollToBottomButtonStyle,
  CSS_KEYFRAMES,
} from '../styles/genAgentChatStyles';

const SHOW_CHAT_LANGUAGE_SELECTOR = true;

/** One completed (or in-progress) live-voice exchange: what the user said + the reply. */
type LiveTurn = { user: string; agent: string; createTime: number };

/** Current time in epoch seconds (the timestamp format ChatMessage expects). */
const nowSec = () => Math.floor(Date.now() / 1000);

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
  brandLogoUrl,
  mode = 'embedded',
  onExitFullscreen,
  floatingConfig = {},
  language,
  translations: customTranslations,
  reCaptchaKey,
  widget = false,
  quickInput = false,
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
  readReceipts = false,
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
  // Keeps the floating panel in the DOM through its close animation before unmounting.
  const [isPanelMounted, setIsPanelMounted] = useState(false);
  // Quick-message input beside the launcher bubble (dismissal persists across loads).
  const [quickInputDismissed, setQuickInputDismissed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    try { return localStorage.getItem('genassist_quick_input_dismissed') === '1'; } catch { return false; }
  });
  const [submittedForms, setSubmittedForms] = useState<Set<number>>(new Set());
  const [submittingFormIndex, setSubmittingFormIndex] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const [headerHeight, setHeaderHeight] = useState(56);
  const [showBacklight, setShowBacklight] = useState(false);

  // Input-bar variant (mode="inputbar"): a docked "Chat Input" that reveals FAQs on
  // focus and expands a conversation panel above itself. `barFocused` drives the FAQ
  // reveal; `barPanelOpen` is the open intent and `barPanelMounted` keeps the panel in
  // the DOM through its close animation.
  const [barFocused, setBarFocused] = useState(false);
  const [barPanelOpen, setBarPanelOpen] = useState(false);
  const [barPanelMounted, setBarPanelMounted] = useState(false);
  // Latest agent reply that arrived while the panel was closed — surfaced as a compact
  // preview card above the bar instead of forcing the whole conversation open.
  const [barReplyPreview, setBarReplyPreview] = useState<string | null>(null);
  // Hover reveals the dismiss (X) affordance on the closed-chat reply preview card.
  const [replyPreviewHovered, setReplyPreviewHovered] = useState(false);
  const inputBarRootRef = useRef<HTMLDivElement>(null);
  // Guards the auto "Start Conversation" that fires the first time the bar is focused on a
  // fresh session, so a single focus can't kick off multiple starts.
  const barStartTriggeredRef = useRef(false);
  // True while the OS file picker is open (opened from the bar). The picker blurs the
  // textarea; this lets us ignore that blur so the bar doesn't collapse mid-upload.
  const barFilePickRef = useRef(false);

  const openBarPanel = useCallback(() => {
    setBarReplyPreview(null);
    setBarPanelMounted(true);
    setBarPanelOpen(true);
  }, []);

  const closeBarPanel = useCallback(() => {
    setBarPanelOpen(false);
  }, []);

  const {
    messages,
    isLoading,
    sendMessage,
    sendAudioMessage,
    uploadFile,
    resetConversation,
    startConversation,
    triggerStartForm,
    shouldTriggerStartForm,
    conversationId,
    guestToken,
    possibleQueries,
    isFinalized,
    isAgentTyping,
    addFeedback,
    readState,
    markRead,
    availableLanguages: agentAvailableLanguages,
    agentId,
    agentLiveVoiceEnabled,
    agentLiveVoiceReady,
    agentGreetOnStart,
    welcomeTitle,
    welcomeImageUrl,
    welcomeMessage,
    inputDisclaimerHtml,
    thinkingPhrases,
    thinkingDelayMs,
    formNodeLocales,
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

  const { messagesEndRef, chatContainerRef, showScrollButton, scrollToLatest } = useScrollManagement({
    messages,
    isAgentTyping,
    currentThinkingPartIndex,
    currentThinkingPartsLength: currentThinkingParts.length,
    conversationId,
    isFloatingOpen: mode === 'inputbar' ? barPanelOpen : isFloatingOpen,
    mode,
  });

  // Report the visitor's read state upstream (so a supervisor sees when their reply
  // was read). Emits only while the chat surface is open, its bottom is on screen,
  // and the tab is focused.
  const { unreadCount, dividerBeforeKey, registerBottom } = useReadReporter({
    enabled: readReceipts,
    active: mode === 'floating' ? isFloatingOpen : mode === 'inputbar' ? barPanelOpen : true,
    messages,
    conversationId,
    isFinalized,
    markRead,
    persistKey:
      readReceipts && conversationId
        ? `genassist_unread_seen:${apiKey}:${conversationId}`
        : null,
  });

  // Attach both the scroll-management ref and the read-tracker's visibility observer
  // to the single bottom sentinel. The observer is driven by this callback (fires on
  // mount/unmount), so it works even when the panel mounts a render after it opens.
  const setBottomSentinelRef = useCallback(
    (el: HTMLDivElement | null) => {
      (messagesEndRef as React.MutableRefObject<HTMLDivElement | null>).current = el;
      registerBottom(el);
    },
    [messagesEndRef, registerBottom],
  );

  // Sequence of the visitor's most recent message (anchored from the update
  // response) — the one that carries the read receipt.
  const lastCustomerSequence = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].speaker === 'customer') {
        return messages[i].sequence_number;
      }
    }
    return undefined;
  }, [messages]);

  // "Seen" only when a human supervisor's marker has reached this message; otherwise
  // "Delivered" once the server assigned it a sequence; "Sent" while still in flight.
  const lastCustomerReceipt = useMemo<'sent' | 'delivered' | 'seen' | undefined>(() => {
    if (!readReceipts) return undefined;
    if (typeof lastCustomerSequence !== 'number') return 'sent';
    const supervisorSeq = readState?.supervisor_last_read_sequence;
    if (typeof supervisorSeq === 'number' && supervisorSeq >= lastCustomerSequence) {
      return 'seen';
    }
    return 'delivered';
  }, [readReceipts, lastCustomerSequence, readState]);

  // Index of the visitor's most recent message, so only it shows the receipt.
  const lastCustomerIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].speaker === 'customer') return i;
    }
    return -1;
  }, [messages]);

  const {
    windowWidth,
    windowHeight,
    isFullscreen,
    handleFullscreenToggle,
    isExpanded,
    handleExpandToggle,
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

  // When a Human In The Loop node with "show_on_start" is wired directly after Start, run
  // the workflow once as the conversation opens so its form appears immediately, before
  // any visitor message. Fires only on a fresh conversation: no visitor messages yet and
  // no form already present (a welcome message may exist; a persisted form must not
  // re-trigger on reload).
  const hasFormRequest = messages.some((m) => m.type === 'form_request');
  const startFormTriggeredRef = useRef(false);
  useEffect(() => {
    if (
      shouldTriggerStartForm &&
      conversationId &&
      !isFinalized &&
      !hasUserMessages &&
      !hasFormRequest &&
      !startFormTriggeredRef.current
    ) {
      startFormTriggeredRef.current = true;
      triggerStartForm(reCaptchaTokenRef.current);
    }
  }, [shouldTriggerStartForm, conversationId, isFinalized, hasUserMessages, hasFormRequest, triggerStartForm]);

  // Allow a fresh trigger after a reset (new conversation id / cleared messages).
  useEffect(() => {
    if (!conversationId) {
      startFormTriggeredRef.current = false;
    }
  }, [conversationId]);

  // Form-submission state is keyed by message index, which is only meaningful within a
  // single conversation. Clear it whenever the conversation changes so a form submitted in
  // a previous conversation doesn't mark a new conversation's form (at the same index) as
  // already answered — which would wrongly hide it on Start (Reset cleared it, plain Start
  // did not). The reload case stays correct: it relies on isFormAnswered's transcript check.
  useEffect(() => {
    setSubmittedForms(new Set());
    setSubmittingFormIndex(null);
  }, [conversationId]);

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

  // Mount the floating panel as soon as it opens; unmount happens on close-animation end.
  useEffect(() => {
    if (mode === 'floating' && isFloatingOpen) {
      setIsPanelMounted(true);
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

  // Input-bar variant: mount the conversation panel as soon as it opens (unmount happens
  // on the close-animation end), and collapse it on Escape or a click outside the widget.
  useEffect(() => {
    if (mode === 'inputbar' && barPanelOpen) {
      setBarPanelMounted(true);
    }
  }, [mode, barPanelOpen]);

  useEffect(() => {
    if (mode !== 'inputbar') return;
    if (typeof window === 'undefined') return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (showResetConfirm) { setShowResetConfirm(false); return; }
      if (showLanguageDropdown) { setShowLanguageDropdown(false); return; }
      if (showMenu) { setShowMenu(false); return; }
      if (barPanelOpen) { closeBarPanel(); return; }
    };
    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      const root = inputBarRootRef.current;
      if (!root) return;
      if (root.contains(e.target as Node)) return;
      // Clicked outside the widget: collapse the panel, close the menu and hide the FAQ list.
      setBarFocused(false);
      setShowMenu(false);
      setShowLanguageDropdown(false);
      if (barPanelOpen) closeBarPanel();
    };

    window.addEventListener('keydown', onKeyDown);
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
    };
  }, [mode, barPanelOpen, showResetConfirm, showMenu, showLanguageDropdown, closeBarPanel]);

  // Input-bar variant: when a fresh agent text reply lands while the panel is closed,
  // surface it as the compact preview card (rather than yanking the whole panel open).
  // Skips the initial load so restored history never triggers a preview.
  const barLastAgentKeyRef = useRef<string | null>(null);
  const barReplyInitRef = useRef(false);
  useEffect(() => {
    if (mode !== 'inputbar') return;

    let lastAgent: ChatMessage | undefined;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      // Any textual agent/supervisor reply — the backend's default segment type is
      // "message", so allow that plus "text"/none; only skip non-text payloads
      // (voice, file, HITL form) that shouldn't preview as a one-line notification.
      if (
        m.speaker === 'agent' &&
        m.text &&
        m.text.trim() &&
        m.type !== 'audio' &&
        m.type !== 'file' &&
        m.type !== 'form_request'
      ) {
        lastAgent = m;
        break;
      }
    }
    const key = lastAgent ? (lastAgent.message_id || String(lastAgent.create_time)) : null;

    if (!barReplyInitRef.current) {
      barReplyInitRef.current = true;
      barLastAgentKeyRef.current = key;
      return;
    }
    if (key && key !== barLastAgentKeyRef.current) {
      barLastAgentKeyRef.current = key;
      // Only preview a genuinely just-arrived reply (create_time ≈ now for WS/poll
      // messages), never an older one surfaced when messages hydrate from storage.
      const nowSec = Date.now() / 1000;
      const isFresh =
        !!lastAgent &&
        typeof lastAgent.create_time === 'number' &&
        nowSec - lastAgent.create_time < 60;
      if (!barPanelOpen && isFresh) {
        setBarReplyPreview(lastAgent!.text);
        // Collapse the docked bar so the arriving preview never leaves it expanded
        // (as if auto-focused). Clicking the bar or the card opens the full chat.
        setBarFocused(false);
      }
    }
  }, [messages, mode, barPanelOpen]);

  // Reset the hover state whenever the preview goes away, so the next one doesn't
  // appear with its dismiss button already revealed.
  useEffect(() => {
    if (!barReplyPreview) setReplyPreviewHovered(false);
  }, [barReplyPreview]);

  // A new conversation clears any stale reply preview.
  useEffect(() => {
    setBarReplyPreview(null);
    barLastAgentKeyRef.current = null;
    // Allow the focus auto-start to fire again once there's no active conversation.
    if (!conversationId) {
      barStartTriggeredRef.current = false;
    }
  }, [conversationId]);

  // Input-bar variant: when the conversation finalizes, just collapse the panel back to the
  // docked bar (no blocking "Start Conversation" button). Focusing the bar afterwards starts
  // a fresh conversation. Also re-arm the focus auto-start so that focus can trigger it.
  useEffect(() => {
    if (mode !== 'inputbar' || !isFinalized) return;
    barStartTriggeredRef.current = false;
    if (barPanelOpen) closeBarPanel();
  }, [mode, isFinalized, barPanelOpen, closeBarPanel]);

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

  type FormSchemaField = {
    name?: string;
    label?: string;
    options?: Array<{ value?: string; label?: string }>;
  };

  // Overlay a form schema with the selected language's strings from the locale bundle
  // (keyed by node id), so a displayed form re-localizes on language switch. Falls back
  // to the schema's own strings when a translation is missing.
  const localizeForm = useCallback(
    (schema: any): any => {
      if (!schema || typeof schema !== 'object') return schema;
      const code = resolvedLanguage.toLowerCase().split('-')[0];
      const slice = formNodeLocales?.[code]?.[schema.node_id];
      if (!slice) return schema;
      return {
        ...schema,
        message: slice.message ?? schema.message,
        fields: Array.isArray(schema.fields)
          ? schema.fields.map((f: any) => {
              const t = f?.name ? slice.fields?.[f.name] : undefined;
              if (!t) return f;
              return {
                ...f,
                label: t.label ?? f.label,
                placeholder: t.placeholder ?? f.placeholder,
                description: t.description ?? f.description,
                options: Array.isArray(f.options)
                  ? f.options.map((o: any) => ({
                      ...o,
                      label: t.options?.[String(o?.value)] ?? o?.label,
                    }))
                  : f.options,
              };
            })
          : schema.fields,
      };
    },
    [resolvedLanguage, formNodeLocales],
  );

  const getFormSchema = (
    messageIndex: number,
  ): { node_id?: string; message?: string; fields?: FormSchemaField[] } | null => {
    const msg = messages[messageIndex];
    if (msg?.type === 'form_request' && msg.text) {
      try { return localizeForm(JSON.parse(msg.text)); } catch { /* skip */ }
    }
    return null;
  };

  const getFormNodeId = (messageIndex: number): string | undefined =>
    getFormSchema(messageIndex)?.node_id;

  // Build the human-readable customer message from the submitted form. We show each field's
  // label, and for option-based fields (e.g. select) the chosen option's label instead of
  // its raw value — both already in the conversation language, since the form schema is
  // translated. The payload (`human_in_the_loop_from_form`) keeps the raw keys/values.
  const buildFormSummary = (
    formData: Record<string, unknown>,
    messageIndex: number,
  ): string => {
    const fieldByName: Record<string, FormSchemaField> = {};
    for (const f of getFormSchema(messageIndex)?.fields ?? []) {
      if (f && typeof f.name === 'string') fieldByName[f.name] = f;
    }
    return Object.entries(formData)
      .map(([key, value]) => {
        const field = fieldByName[key];
        const label = field?.label || key;
        const option = field?.options?.find(
          (o) => o && String(o.value) === String(value),
        );
        const display = option?.label || value;
        return `${label}: ${display}`;
      })
      .join('\n');
  };

  const handleFormSubmit = async (formData: Record<string, unknown>, messageIndex: number) => {
    if (submittingFormIndex !== null || isAgentTyping) return;
    setSubmittingFormIndex(messageIndex);
    try {
      const summaryText = buildFormSummary(formData, messageIndex);
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

  // Neutral, user-facing notice shown when a live call can't start / fails. The
  // message is already neutral (the backend never sends internal config detail), so
  // it's safe for public widgets — it just avoids a confusing silent close.
  const [liveVoiceNotice, setLiveVoiceNotice] = useState<string | null>(null);

  const handleVoiceError = (error: Error) => {
    setLiveVoiceNotice(error.message || 'Voice is currently unavailable');
    if (onError) {
      onError(error);
    }
  };

  // Voice-only mode is driven purely by the agent: it's on when the agent's
  // workflow contains a Voice Agent node (auto-detected by the backend and
  // surfaced through `agentLiveVoiceEnabled`). No integrator prop is involved.
  const liveVoiceEnabled = agentLiveVoiceEnabled;
  // Whether live voice can actually run (a Gemini provider with a key is configured).
  // When false we keep voice-only mode but disable the call control with a neutral
  // message — the specific reason stays server-side, never shown to public users.
  const liveVoiceReady = agentLiveVoiceReady;

  // Live (continuous) voice conversation against the agent's Voice Agent node.
  // `liveCaption` is the in-progress turn (streams as you speak); `liveTurns` are
  // completed turns kept locally so they stay on screen across turns. `createTime`
  // is captured once per turn so the bubble timestamp doesn't jitter on re-render.
  const [liveCaption, setLiveCaption] = useState<LiveTurn>({ user: '', agent: '', createTime: 0 });
  const [liveTurns, setLiveTurns] = useState<LiveTurn[]>([]);
  const liveVoice = useLiveVoiceSession({
    baseUrl,
    apiKey,
    guestToken,
    tenant,
    agentId,
    conversationId,
    language: resolvedLanguage,
    onError: handleVoiceError,
    onInputTranscript: (text) =>
      setLiveCaption((c) => ({ ...c, user: c.user + text, createTime: c.createTime || nowSec() })),
    onOutputTranscript: (text) =>
      setLiveCaption((c) => ({ ...c, agent: c.agent + text, createTime: c.createTime || nowSec() })),
    onTurnComplete: (turn) => {
      // Commit the finished turn so it stays visible; clear the in-progress caption.
      setLiveTurns((prev) => [...prev, { user: turn.transcript, agent: turn.response, createTime: nowSec() }]);
      setLiveCaption({ user: '', agent: '', createTime: 0 });
    },
  });

  // Full conversation reset: new thread + cleared input/attachments/forms and any
  // live-voice transcript. Shared by the reset-confirm dialog and the end-call button.
  const performReset = useCallback(async () => {
    setInputValue('');
    clearAttachments();
    await resetConversation(reCaptchaTokenRef.current);
    setSelectedFaqQuery(null);
    setSubmittedForms(new Set());
    setSubmittingFormIndex(null);
    setLiveTurns([]);
  }, [clearAttachments, resetConversation]);

  // Starting a fresh call clears the previous call's transcript bubbles + caption.
  const startLiveCall = useCallback(() => {
    setLiveVoiceNotice(null);
    setLiveCaption({ user: '', agent: '', createTime: 0 });
    setLiveTurns([]);
    liveVoice.start();
  }, [liveVoice]);
  // Ending a call stops the audio stream and resets the conversation — same as the
  // "reset conversation" action — so the next call starts from a clean thread.
  const endLiveCall = useCallback(() => {
    liveVoice.stop();
    setLiveCaption({ user: '', agent: '', createTime: 0 });
    void performReset();
  }, [liveVoice, performReset]);

  // Keep the live transcript in view as it grows (the scroll manager only reacts
  // to committed chat messages, not these local live bubbles).
  useEffect(() => {
    if (!liveVoice.isActive) return;
    const el = chatContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [liveCaption, liveTurns, liveVoice.isActive, chatContainerRef]);

  // Render a single live-voice bubble (committed turn or streaming caption) as an
  // ordinary chat message, so it looks identical to text-mode bubbles.
  const renderLiveBubble = (
    speaker: 'customer' | 'agent',
    text: string,
    createTime: number,
    key?: string,
  ) => (
    <ChatMessageComponent
      key={key}
      message={{ create_time: createTime, start_time: 0, end_time: 0.01, speaker, text }}
      theme={theme}
      enableTypewriter={false}
      translations={translations}
      language={resolvedLanguage}
      agentName={agentName}
    />
  );

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

  const handleDismissQuickInput = () => {
    setQuickInputDismissed(true);
    try { localStorage.setItem('genassist_quick_input_dismissed', '1'); } catch { /* ignore */ }
  };

  // Quick input next to the bubble: open the panel, start a conversation if needed, then send.
  const handleQuickInputSend = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setIsFloatingOpen(true);
    try {
      if (!conversationId) {
        await startConversation(reCaptchaTokenRef.current);
      }
      await sendMessage(trimmed, [], undefined, reCaptchaTokenRef.current);
    } catch (error) {
      // ignore
    }
  };

  // ===== Input-bar variant (mode="inputbar") handlers =====

  // Focusing the bar: continue an existing conversation (open the panel), or — on a fresh
  // session — kick off "Start Conversation" so the welcome / FAQs load and the visitor can
  // pick a suggestion or type right away. A reply preview keeps the panel closed so the
  // visitor can read it / reply inline.
  const handleBarFocus = () => {
    // While a reply preview is showing, ignore focus entirely — expanding or opening
    // the chat must come from an explicit click (the bar or the card), never a
    // possibly-programmatic focus. Keeps the docked bar compact until the visitor acts.
    if (barReplyPreview) return;
    setBarFocused(true);
    // Finalized conversation: the previous chat is over, so focusing the docked bar starts a
    // fresh one (the old "Start Conversation" action) rather than reopening the ended panel.
    // startConversation resets state and flips isFinalized off; the greeting agent opens the
    // panel up front so its greeting has somewhere to land.
    if (isFinalized) {
      if (!isLoading && !barStartTriggeredRef.current) {
        barStartTriggeredRef.current = true;
        if (agentGreetOnStart) openBarPanel();
        void startConversation(reCaptchaTokenRef.current);
      }
      return;
    }
    // Agent greets on start: open the conversation panel (agent typing → greeting) instead of
    // showing FAQs, and start the conversation if fresh so the greeting trigger fires. The
    // greeting then lands in the already-open panel rather than as a compact reply card.
    if (agentGreetOnStart) {
      openBarPanel();
      if (!conversationId && !isLoading && !barStartTriggeredRef.current) {
        barStartTriggeredRef.current = true;
        void startConversation(reCaptchaTokenRef.current);
      }
      return;
    }
    if (hasUserMessages) {
      openBarPanel();
      return;
    }
    if (!conversationId && !isFinalized && !isLoading && !barStartTriggeredRef.current) {
      barStartTriggeredRef.current = true;
      void startConversation(reCaptchaTokenRef.current);
    }
  };

  // Open the full conversation from the compact agent-reply preview card.
  const openBarFromPreview = () => {
    openBarPanel();
  };

  // Send from the docked bar: open the panel, start a conversation if needed, then send.
  const submitBarMessage = async () => {
    if ((inputValue.trim() === '' && attachments.length === 0) || isAgentTyping || hasPendingForm) return;
    const textToSend = inputValue;
    const filesToUpload = attachments.map(a => a.file);

    setInputValue('');
    setAttachments([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    openBarPanel();

    try {
      if (!conversationId) {
        await startConversation(reCaptchaTokenRef.current);
      }
      const extraMetadata: Record<string, any> = {};
      if (selectedFaqQuery) {
        extraMetadata.faq_query = selectedFaqQuery;
      }
      if (filesToUpload.length > 0) {
        extraMetadata.attachments = attachments.map(a => a.attachment);
      }
      await sendMessage(
        textToSend,
        filesToUpload,
        Object.keys(extraMetadata).length > 0 ? extraMetadata : undefined,
        reCaptchaTokenRef.current,
      );
    } catch (error) {
      // ignore
    } finally {
      setTimeout(() => textAreaRef.current?.focus(), 0);
    }
  };

  // FAQ chip clicked from the bar: open the panel, start a conversation if needed, then send.
  const handleBarQueryClick = async (query: string) => {
    if (isAgentTyping || isLoading) return;
    setSelectedFaqQuery(query);
    openBarPanel();
    try {
      if (!conversationId) {
        await startConversation(reCaptchaTokenRef.current);
      }
      await sendMessage(query, [], { faq_query: query }, reCaptchaTokenRef.current);
    } catch (error) {
      // ignore
    }
  };

  // Attach clicked from the bar: keep the chat open/expanded in both focused and collapsed
  // states while the OS file dialog is open. The dialog blurs the textarea, so we set a guard
  // (honored by the textarea onBlur) and re-focus once the window regains focus (pick/cancel).
  const handleBarAttachClick = () => {
    // Mark the picker open (so the upcoming blur is ignored) and open the dialog FIRST —
    // synchronously, before any state work — so the browser keeps the click's user
    // activation, which is required to open a file dialog.
    barFilePickRef.current = true;
    fileInputRef.current?.click();
    // Then keep the bar active / open the panel / start a conversation as appropriate.
    handleBarFocus();
    const onWindowFocus = () => {
      window.removeEventListener('focus', onWindowFocus);
      barFilePickRef.current = false;
      setBarFocused(true);
      setTimeout(() => textAreaRef.current?.focus(), 0);
    };
    window.addEventListener('focus', onWindowFocus);
  };

  const handleMenuClick = () => {
    setShowMenu(prev => !prev);
  };

  const handleResetClick = () => {
    setShowMenu(false);
    setShowResetConfirm(true);
  };

  const handleConfirmReset = () => {
    setShowResetConfirm(false);
    // endLiveCall stops any active call and runs the full reset; harmless if no
    // call is active, so both entry points share one code path.
    endLiveCall();
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
  const { primaryColor, secondaryColor, backgroundColor, textColor, fontFamily, fontSize, borderColor, mutedTextColor, inputBackgroundColor } = themeParams;
  const fontSizeNumber = typeof fontSize === 'string' ? parseInt(fontSize, 10) : (typeof fontSize === 'number' ? fontSize : 14);

  const position = floatingConfig.position || 'bottom-right';
  const offset = floatingConfig.offset || { x: 20, y: 20 };
  const offsetX = offset.x || 20;
  const offsetY = offset.y || 20;

  const isFloatingDocked = mode === 'floating' && !isFullscreen;

  // Computed styles
  const containerStyle = getContainerStyle({ isFullscreen, isFloatingDocked, windowWidth, t: themeParams });
  const headerStyle = getHeaderStyle(themeParams);
  const headerPillTitleStyle = getHeaderPillTitleStyle(fontFamily, textColor);
  const headerDescriptionTextStyle = getHeaderDescriptionTextStyle(fontFamily, mutedTextColor);
  const headerDescription = (description ?? t('header.subtitle') ?? '').trim();
  const brandLogo = brandLogoUrl?.trim() ?? '';
  const hasBrandLogo = brandLogo.length > 0;
  // Description reveal only applies to the small-logo layout; the full brand logo replaces the text.
  const hasHeaderDescription = !hasBrandLogo && headerDescription.length > 0;
  const menuPopupStyle = getMenuPopupStyle(backgroundColor, borderColor);
  const menuItemStyle = getMenuItemStyle(themeParams);
  // Hover fill for menu items / outline buttons — theme-aware, matches the web app's bg-accent.
  const menuHoverBg = theme?.secondaryColor || '#f4f4f5';
  const contentCardStyle = getContentCardStyle(backgroundColor);
  const sendButtonStyle = getSendButtonStyle(primaryColor);

  // "New messages" separator rendered above the first message the visitor hasn't
  // seen since they last left the conversation (read receipts only).
  const renderNewMessagesDivider = () => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', margin: '12px 0' }}>
      <div style={{ flex: 1, height: 1, backgroundColor: primaryColor, opacity: 0.35 }} />
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: primaryColor,
          whiteSpace: 'nowrap',
        }}
      >
        {t('receipts.newMessages', 'New messages')}
      </span>
      <div style={{ flex: 1, height: 1, backgroundColor: primaryColor, opacity: 0.35 }} />
    </div>
  );

  const possibleQueriesContainerStyle = getPossibleQueriesContainerStyle(fontFamily);
  const queryButtonStyle = getQueryButtonStyle(themeParams);
  const confirmOverlayStyle = getConfirmOverlayStyle(showResetConfirm);
  const confirmDialogStyle = getConfirmDialogStyle(themeParams);
  const disclaimerStyle = getDisclaimerStyle(fontFamily, mutedTextColor);
  const inputContainerStyle = getInputContainerStyle(inputBackgroundColor);
  const inputWrapperStyle = getInputWrapperStyle(inputBackgroundColor, borderColor);

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

  // A form_request is "answered" once the visitor has responded to it. Besides the
  // optimistic in-session flag (`submittedForms`), we also treat it as answered when a
  // later customer message exists — that survives a page reload (where `submittedForms`
  // is gone), so a completed form never reappears after refresh.
  const isFormAnswered = (index: number): boolean => {
    if (submittedForms.has(index)) return true;
    for (let j = index + 1; j < messages.length; j++) {
      if (messages[j].speaker === 'customer') return true;
    }
    return false;
  };

  const hasPendingForm = messages.some(
    (msg, idx) =>
      msg.type === 'form_request' && msg.speaker === 'agent' && !isFormAnswered(idx),
  );

  const pendingForm = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.type === 'form_request' && msg.speaker === 'agent' && !isFormAnswered(i)) {
        try { return { schema: localizeForm(JSON.parse(msg.text)), index: i }; }
        catch { /* skip */ }
      }
    }
    return null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, submittedForms, localizeForm]);

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
    isExpanded,
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

  // Shared message-list body: synthetic welcome + message map (incl. inline forms) +
  // thinking indicator + live-voice turns. Rendered inside the scrollable chat container
  // by both the standard panel and the input-bar variant, so message behaviour stays
  // identical across modes.
  const renderConversationBody = () => (
    <>
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

        // Live-voice turns are rendered locally (below) the moment they finish.
        // Each is also persisted and broadcast back into `messages`; suppress that
        // copy so a turn isn't shown twice (and never blinks as the two swap).
        const liveTurnKeys = new Set<string>();
        for (const turn of liveTurns) {
          if (turn.user.trim()) liveTurnKeys.add(`customer:${turn.user.trim()}`);
          if (turn.agent.trim()) liveTurnKeys.add(`agent:${turn.agent.trim()}`);
        }

        const applyMessageFilter = (message: ChatMessage) => {
          if (message.type === 'file') return false;
          if (liveTurnKeys.has(`${message.speaker}:${(message.text || '').trim()}`)) return false;
          return true;
        }

        return messages.filter(applyMessageFilter).map((message, index) => {
          const showNewDivider = !!dividerBeforeKey && messageIdentityKey(message) === dividerBeforeKey;
          if (message.type === 'form_request' && message.speaker === 'agent') {
            try {
              const formSchema = localizeForm(JSON.parse(message.text));
              // Use the real message position (filtering can shift the map index) so the
              // answered check matches the overlay/footer path and survives reload.
              const originalIndex = messages.indexOf(message);
              const isPending = !isFormAnswered(originalIndex);
              return (
                <React.Fragment key={index}>
                  {showNewDivider && renderNewMessagesDivider()}
                  <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '85%', marginBottom: '8px' }}>
                    <div style={{ fontSize: '14px', color: textColor, fontWeight: 600, marginBottom: 4 }}>
                      {agentName || 'Agent'}
                    </div>
                    {formDisplay === 'inline' && isPending ? (
                      <DynamicFormMessage
                        schema={formSchema}
                        onSubmit={(data) => handleFormSubmit(data, originalIndex)}
                        onCancel={() => handleFormCancel(originalIndex)}
                        isSubmitting={submittingFormIndex === originalIndex}
                        isSubmitted={false}
                        primaryColor={primaryColor}
                        fontFamily={fontFamily}
                        backgroundColor={backgroundColor}
                        textColor={textColor}
                        borderColor={borderColor}
                        mutedTextColor={mutedTextColor}
                        inputBackgroundColor={inputBackgroundColor}
                        variant="card"
                      />
                    ) : (
                      <div style={{
                        backgroundColor: secondaryColor,
                        borderRadius: '12px',
                        padding: '10px 14px',
                        fontSize: '14px',
                        color: textColor,
                        fontFamily,
                      }}>
                        {formSchema.message || 'Please fill the form below.'}
                      </div>
                    )}
                  </div>
                </React.Fragment>
              );
            } catch {
              // Fall through to normal rendering if JSON parse fails
            }
          }

          const isNextSameSpeaker = index < messages.length - 1 && messages[index + 1].speaker === message.speaker;
          const isPrevSameSpeaker = index > 0 && messages[index - 1].speaker === message.speaker;
          // When the agent greets on start, that greeting is a normal reply — not the
          // "welcome" message — so don't give it the first-message welcome treatment
          // (which would split its text into a big title + body).
          const isFirstAgentMessage =
            index === firstAgentIndex && message.speaker === 'agent' && !hasUserMessages && !shouldTriggerStartForm;
          const displayMessage =
            isFirstAgentMessage && welcomeMessage
              ? { ...message, text: welcomeMessage }
              : message;

          return (
            <React.Fragment key={index}>
              {showNewDivider && renderNewMessagesDivider()}
              <ChatMessageComponent
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
                receiptStatus={index === lastCustomerIndex ? lastCustomerReceipt : undefined}
              />
            </React.Fragment>
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
                color: mutedTextColor,
                fontSize: '13px',
              }}
            >
              {currentThinkingParts[currentThinkingPartIndex] || currentThinkingParts[currentThinkingParts.length - 1]}
            </div>
          </div>
        </div>
      )}
      {/* Completed live-voice turns, rendered as ordinary chat bubbles and kept
          in local state so they stay visible across turns. The persisted copy of
          each turn is filtered out of `messages` above, so these are the single
          source of truth on screen — they never get hidden, so nothing blinks. */}
      {liveTurns.map((turn, i) => (
        <React.Fragment key={`live-turn-${i}`}>
          {turn.user.trim() !== '' && renderLiveBubble('customer', turn.user, turn.createTime)}
          {turn.agent.trim() !== '' && renderLiveBubble('agent', turn.agent, turn.createTime)}
        </React.Fragment>
      ))}
      {/* In-progress turn: streams the partial transcript live (ChatMessage now
          tracks its text prop, so these update in place as chunks arrive). */}
      {liveVoice.isActive && liveCaption.user.trim() !== '' &&
        renderLiveBubble('customer', liveCaption.user, liveCaption.createTime, '__live_caption_user__')}
      {liveVoice.isActive && liveCaption.agent.trim() !== '' &&
        renderLiveBubble('agent', liveCaption.agent, liveCaption.createTime, '__live_caption_agent__')}
      <div ref={setBottomSentinelRef} />
    </>
  );

  const renderChatComponent = () => (
    <div style={{ ...containerStyle, ['--ga-hover' as string]: menuHoverBg }} data-genassist-root="true">
      <style>{CSS_KEYFRAMES}</style>
      <div className="ga-header" style={headerStyle} ref={headerRef}>
        {/* Left: hidden expand button (revealed on hover) + logo/name group.
            Hovering this section expands the button from 0 width, sliding the group right. */}
        <div className="ga-header-left" style={headerLeftContainerStyle}>
          {mode === 'floating' && !isFullscreen && windowWidth > 768 && (
            <button
              className="ga-header-btn ga-header-expand-btn"
              style={{ ...menuButtonStyle, width: undefined, flexShrink: 0 }}
              onClick={handleExpandToggle}
              title={isExpanded ? t('menu.collapse', 'Collapse') : t('menu.expand', 'Expand')}
              aria-label={isExpanded ? t('menu.collapse', 'Collapse') : t('menu.expand', 'Expand')}
            >
              {isExpanded ? (
                <Minimize2 size={20} color={textColor} />
              ) : (
                <Maximize2 size={20} color={textColor} />
              )}
            </button>
          )}

          <div
            style={headerPillStyle}
            tabIndex={hasHeaderDescription ? 0 : undefined}
          >
            {hasBrandLogo ? (
              <img src={brandLogo} alt={headerTitle} style={brandLogoStyle} />
            ) : (
              <>
                <img src={logoUrl?.trim() || chatLogo} alt="Logo" style={logoStyle} />
                <div style={headerPillTextColumnStyle}>
                  <span style={headerPillTitleStyle} title={headerTitle}>{headerTitle}</span>
                  {hasHeaderDescription && (
                    <div className="ga-header-desc">
                      <div className="ga-header-desc-inner">
                        <span
                          className="ga-header-desc-text"
                          style={{ ...headerDescriptionTextStyle, display: 'block' }}
                        >
                          {headerDescription}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right: menu + close */}
        <div style={headerRightContainerStyle}>
          <button
            className="ga-header-btn"
            style={menuButtonStyle}
            onClick={handleMenuClick}
            title={t('menu.title')}
          >
            <MoreHorizontal size={22} color={textColor} />
          </button>
          {mode === 'floating' && (
            <button
              className="ga-header-btn"
              style={menuButtonStyle}
              onClick={() => setIsFloatingOpen(false)}
              title="Close chat"
            >
              <X size={22} color={textColor} />
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
          <div className="ga-menu-item" style={menuItemStyle} onClick={handleResetClick}>
            <RefreshCw size={16} />
            {t('menu.resetConversation')}
          </div>
          {mode !== 'fullscreen' && (
            <div className="ga-menu-item" style={menuItemStyle} onClick={handleFullscreenToggle}>
              <Fullscreen size={16} />
              {t('menu.fullscreen')}
            </div>
          )}
          {hasLanguageOptions && (
            <div
              className="ga-menu-item"
              style={{ ...menuItemStyle, position: 'relative' }}
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
                    borderRadius: '10px',
                    border: `1px solid ${borderColor}`,
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
                    padding: '4px',
                    minWidth: '180px',
                    maxWidth: '200px',
                    overflow: 'hidden',
                    zIndex: 1001,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {availableLanguages.map((lang) => (
                    <div
                      key={lang.code}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '6px 8px',
                        borderRadius: '8px',
                        color: textColor,
                        backgroundColor: resolvedLanguage === lang.code
                          ? menuHoverBg
                          : 'transparent',
                        cursor: 'pointer',
                        fontSize,
                        fontFamily,
                        transition: 'background-color 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (resolvedLanguage !== lang.code) {
                          e.currentTarget.style.backgroundColor = menuHoverBg;
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
        <div className="ga-scroll" style={chatContainerStyle} ref={chatContainerRef}>
          {renderLanguageSelector()}

          {renderConversationBody()}
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

        {liveVoiceNotice && (
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
            <span>{liveVoiceNotice}</span>
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
                backgroundColor={secondaryColor}
                textColor={textColor}
                mutedTextColor={mutedTextColor}
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
        ) : liveVoiceEnabled ? (
          // Live voice mode is voice-only: no text box, attach, or send button —
          // the only way to talk to the agent is to start a live call.
          <div style={inputContainerStyle}>
            <div style={{ display: 'flex', flexDirection: 'column', width: '100%', minWidth: 0 }}>
              <div style={inputWrapperStyle}>
                <span style={getLiveVoiceHintStyle(textAreaFontSize, fontFamily, mutedTextColor)}>
                  {liveVoiceReady
                    ? t('liveVoice.tapToStart', 'Tap to start a voice conversation')
                    : t('liveVoice.unavailable', 'Voice is currently unavailable')}
                </span>
                <LiveCallControl
                  status={liveVoice.status}
                  isActive={liveVoice.isActive}
                  onStart={startLiveCall}
                  onStop={endLiveCall}
                  theme={theme}
                  disabled={!agentId || !liveVoiceReady}
                />
              </div>
              {agentDisclaimerContent && (
                <div className="ga-input-disclaimer" style={disclaimerStyle}>
                  {agentDisclaimerContent}
                </div>
              )}
            </div>
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
                    <Paperclip size={22} color={mutedTextColor} />
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

        {/* Full-screen form: when a Human In The Loop form is pending, it takes over the
            whole chat panel (the node's message shown as a heading on top) instead of a
            cramped footer. Inline mode keeps rendering the form within the message list. */}
        {pendingForm && formDisplay !== 'inline' && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              zIndex: 30,
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: backgroundColor || '#ffffff',
            }}
          >
            <DynamicFormMessage
              schema={pendingForm.schema}
              onSubmit={(data) => handleFormSubmit(data, pendingForm.index)}
              onCancel={() => handleFormCancel(pendingForm.index)}
              isSubmitting={submittingFormIndex === pendingForm.index}
              isSubmitted={false}
              primaryColor={primaryColor}
              fontFamily={fontFamily}
              backgroundColor={backgroundColor}
              textColor={textColor}
              borderColor={borderColor}
              mutedTextColor={mutedTextColor}
              inputBackgroundColor={inputBackgroundColor}
              variant="fullscreen"
              title={agentName || undefined}
            />
          </div>
        )}
      </div>

      <div style={confirmOverlayStyle}>
        <div style={confirmDialogStyle}>
          <h3 style={{ fontFamily, margin: 0, fontSize: '18px', fontWeight: 600 }}>{t('dialog.resetConversation.title')}</h3>
          <p style={{ fontFamily, fontSize: '14px', color: mutedTextColor, margin: '8px 0 0' }}>{t('dialog.resetConversation.message')}</p>
          <div style={confirmButtonsStyle}>
            <button className="ga-confirm-btn--cancel" style={{ ...getConfirmButtonStyle(false, themeParams), color: textColor }} onClick={handleCancelReset}>{t('buttons.cancel')}</button>
            <button className="ga-confirm-btn--danger" style={getConfirmButtonStyle(true, themeParams)} onClick={handleConfirmReset}>{t('buttons.reset')}</button>
          </div>
        </div>
      </div>
    </div>
  );

  // ===== Input-bar variant (mode="inputbar") =====
  // A docked "Chat Input" pill. Focusing it reveals the agent FAQs (fresh session) or
  // reopens the conversation; sending a message expands a conversation panel above the bar.
  // Reuses the same message body, forms, reset dialog and connection wiring as the panel.
  const renderInputBarComponent = () => {
    const showReplyPreview = Boolean(barReplyPreview) && !barPanelMounted && !isFinalized;
    const barPlaceholder =
      placeholder ||
      (showReplyPreview
        ? t('inputbar.reply', 'Write a reply...')
        : hasUserMessages
          ? t('inputbar.continue', 'Write a message..')
          : inputPlaceholder);
    // FAQs show while the visitor hasn't sent anything yet (a welcome message may exist).
    // Never show them when the agent greets on start — that click opens the panel instead
    // (and guards against the pre-start locale FAQs leaking through before start suppresses them).
    const showFaqs = barFocused && !barPanelOpen && !hasUserMessages && !isFinalized && !agentGreetOnStart && possibleQueries.length > 0;
    const barPanelClosing = barPanelMounted && !barPanelOpen;
    const barLogoSrc = logoUrl?.trim() || chatLogo;
    // Transparent version of the panel background for the top-of-messages fade gradient.
    const barFadeTo = /^#[0-9a-fA-F]{6}$/.test(backgroundColor)
      ? hexToRgba(backgroundColor, 0)
      : 'rgba(255, 255, 255, 0)';
    // Collapsed the bar is compact and centered; on focus / while the panel is open it
    // widens to fill the container. Centering makes it grow out on both sides.
    const isBarActive = barFocused || barPanelOpen;

    return (
      <div
        ref={inputBarRootRef}
        data-genassist-root="true"
        data-genassist-container="inputbar"
        style={{
          // Dock the bar to the bottom-center of the viewport so it stays visible on
          // scroll. Always centered — the input bar ignores floatingConfig corners.
          ...getInputBarRootStyle(fontFamily, offsetY),
          ['--ga-hover' as string]: menuHoverBg,
        }}
      >
        <style>{CSS_KEYFRAMES}</style>

        {/* Conversation panel — grows up from the bar. */}
        {barPanelMounted && (
          <div
            className={barPanelClosing ? 'ga-inbar-panel-out' : 'ga-inbar-panel-in'}
            onAnimationEnd={(e) => {
              if (e.target !== e.currentTarget) return;
              if (barPanelClosing) setBarPanelMounted(false);
            }}
            style={getInputBarPanelStyle(backgroundColor, borderColor)}
            data-genassist-container="inputbar-panel"
          >
            <div style={getInputBarPanelHeaderStyle(backgroundColor)} ref={headerRef}>
              {hasBrandLogo ? (
                <img src={brandLogo} alt={headerTitle} style={brandLogoStyle} />
              ) : (
                <>
                  <img src={barLogoSrc} alt="Logo" style={logoStyle} />
                  <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
                    <span style={headerPillTitleStyle} title={headerTitle}>{headerTitle}</span>
                    {headerDescription.length > 0 && (
                      <span style={{ ...headerDescriptionTextStyle, display: 'block' }} title={headerDescription}>
                        {headerDescription}
                      </span>
                    )}
                  </div>
                </>
              )}
              {hasBrandLogo && <div style={{ flex: 1 }} />}
              <button
                className="ga-header-btn"
                style={menuButtonStyle}
                onClick={handleMenuClick}
                title={t('menu.title')}
                aria-label={t('menu.title')}
              >
                <MoreHorizontal size={22} color={textColor} />
              </button>
              <button
                className="ga-header-btn"
                style={menuButtonStyle}
                onClick={closeBarPanel}
                title={t('menu.collapse', 'Collapse')}
                aria-label={t('menu.collapse', 'Collapse')}
              >
                <ChevronDown size={20} color={textColor} />
              </button>

              {/* Same 3-dots menu as the standard chat, minus fullscreen/maximize. */}
              {showMenu && (
                <div ref={menuRef} style={menuPopupStyle}>
                  <div className="ga-menu-item" style={menuItemStyle} onClick={handleResetClick}>
                    <RefreshCw size={16} />
                    {t('menu.resetConversation')}
                  </div>
                  {hasLanguageOptions && (
                    <div
                      className="ga-menu-item"
                      style={{ ...menuItemStyle, position: 'relative' }}
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
                            borderRadius: '10px',
                            border: `1px solid ${borderColor}`,
                            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
                            padding: '4px',
                            minWidth: '180px',
                            maxWidth: '200px',
                            overflow: 'hidden',
                            zIndex: 1001,
                          }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {availableLanguages.map((lang) => (
                            <div
                              key={lang.code}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '6px 8px',
                                borderRadius: '8px',
                                color: textColor,
                                backgroundColor: resolvedLanguage === lang.code ? menuHoverBg : 'transparent',
                                cursor: 'pointer',
                                fontSize,
                                fontFamily,
                                transition: 'background-color 0.15s ease',
                              }}
                              onMouseEnter={(e) => {
                                if (resolvedLanguage !== lang.code) {
                                  e.currentTarget.style.backgroundColor = menuHoverBg;
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
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, position: 'relative', backgroundColor }}>
              <div className="ga-inbar-body ga-scroll" style={chatContainerStyle} ref={chatContainerRef}>
                {renderConversationBody()}
              </div>
              {/* Soft fade + blur at the top of the message list so messages dissolve under
                  the header instead of hitting a hard border. */}
              <div
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '36px',
                  pointerEvents: 'none',
                  zIndex: 5,
                  background: `linear-gradient(to bottom, ${backgroundColor} 12%, ${barFadeTo} 100%)`,
                  backdropFilter: 'blur(3px)',
                  WebkitBackdropFilter: 'blur(3px)',
                  maskImage: 'linear-gradient(to bottom, #000 40%, transparent 100%)',
                  WebkitMaskImage: 'linear-gradient(to bottom, #000 40%, transparent 100%)',
                }}
              />

              {/* Jump-to-latest: appears when the visitor scrolls up in a scrollable
                  conversation; clicking snaps back to the newest message. */}
              {showScrollButton && (
                <button
                  type="button"
                  className="ga-scroll-bottom-btn"
                  style={getScrollToBottomButtonStyle(backgroundColor)}
                  onClick={() => scrollToLatest()}
                  title={t('inputbar.scrollToBottom', 'Scroll to latest')}
                  aria-label={t('inputbar.scrollToBottom', 'Scroll to latest')}
                >
                  <ArrowDown size={18} color={textColor} />
                </button>
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

              {pendingForm && formDisplay !== 'inline' && (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    zIndex: 30,
                    display: 'flex',
                    flexDirection: 'column',
                    backgroundColor: backgroundColor || '#ffffff',
                  }}
                >
                  <DynamicFormMessage
                    schema={pendingForm.schema}
                    onSubmit={(data) => handleFormSubmit(data, pendingForm.index)}
                    onCancel={() => handleFormCancel(pendingForm.index)}
                    isSubmitting={submittingFormIndex === pendingForm.index}
                    isSubmitted={false}
                    primaryColor={primaryColor}
                    fontFamily={fontFamily}
                    backgroundColor={backgroundColor}
                    textColor={textColor}
                    borderColor={borderColor}
                    mutedTextColor={mutedTextColor}
                    inputBackgroundColor={inputBackgroundColor}
                    variant="fullscreen"
                    title={agentName || undefined}
                  />
                </div>
              )}
            </div>

            <div style={confirmOverlayStyle}>
              <div style={confirmDialogStyle}>
                <h3 style={{ fontFamily, margin: 0, fontSize: '18px', fontWeight: 600 }}>{t('dialog.resetConversation.title')}</h3>
                <p style={{ fontFamily, fontSize: '14px', color: mutedTextColor, margin: '8px 0 0' }}>{t('dialog.resetConversation.message')}</p>
                <div style={confirmButtonsStyle}>
                  <button className="ga-confirm-btn--cancel" style={{ ...getConfirmButtonStyle(false, themeParams), color: textColor }} onClick={handleCancelReset}>{t('buttons.cancel')}</button>
                  <button className="ga-confirm-btn--danger" style={getConfirmButtonStyle(true, themeParams)} onClick={handleConfirmReset}>{t('buttons.reset')}</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Agent-reply preview — shown when a response arrives while the panel is closed.
            Clicking it opens the full conversation. */}
        {showReplyPreview && (
          <div
            role="button"
            tabIndex={0}
            className="ga-inbar-reply"
            style={{
              ...getInputBarReplyCardStyle(backgroundColor, borderColor),
              // Fixed compact notification width — never expands with the bar's active state.
              width: 'min(400px, 100%)',
              margin: '0 auto',
            }}
            onClick={openBarFromPreview}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                openBarFromPreview();
              }
            }}
            onMouseEnter={() => setReplyPreviewHovered(true)}
            onMouseLeave={() => setReplyPreviewHovered(false)}
            aria-label={t('inputbar.viewReply', 'View reply')}
          >
            {hasBrandLogo ? (
              <img src={brandLogo} alt={headerTitle} style={{ height: 36, width: 'auto', maxWidth: 44, objectFit: 'contain', flexShrink: 0 }} />
            ) : (
              <img src={barLogoSrc} alt="Logo" style={{ width: 40, height: 40, borderRadius: 10, objectFit: 'cover', flexShrink: 0 }} />
            )}
            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
              <span
                style={{
                  fontSize: '15px',
                  fontWeight: 600,
                  color: textColor,
                  fontFamily,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {barReplyPreview}
              </span>
              <span style={{ fontSize: '13px', color: mutedTextColor, fontFamily, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {(headerTitle || agentName || t('labels.agent')) + ' · ' + t('inputbar.justNow', 'Just now')}
              </span>
            </div>
            {(replyPreviewHovered || windowWidth <= 768) && (
              <button
                type="button"
                aria-label={t('inputbar.dismissReply', 'Dismiss')}
                onClick={(e) => {
                  e.stopPropagation();
                  setBarReplyPreview(null);
                }}
                style={{
                  position: 'absolute',
                  top: -8,
                  right: -8,
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  background: backgroundColor,
                  border: `1px solid ${borderColor}`,
                  boxShadow: '0 2px 6px rgba(0, 0, 0, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  padding: 0,
                  color: mutedTextColor,
                  zIndex: 1,
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>
        )}

        {/* FAQ chips — shown on focus for a fresh session. */}
        {showFaqs && (
          <div style={getInputBarFaqListStyle()}>
            {possibleQueries.map((query, i) => (
              <button
                key={i}
                className="ga-inbar-faq ga-inbar-faq-btn"
                style={{ ...getInputBarFaqChipStyle(themeParams), animationDelay: `${i * 90}ms` }}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleBarQueryClick(query)}
                disabled={isLoading || isAgentTyping}
              >
                {query}
              </button>
            ))}
          </div>
        )}

        {/* The docked "Chat Input" bar — always shown, even after the conversation is
           finalized: focusing it then starts a fresh conversation (see handleBarFocus).
           Staged attachments preview inside the card, above the input row — same approach as
           floating/embedded mode. */}
        <form
          className="ga-inbar-bar"
          onSubmit={(e) => { e.preventDefault(); submitBarMessage(); }}
          style={{
            ...getInputBarBarStyle(inputBackgroundColor, borderColor),
            flexDirection: 'column',
            alignItems: 'stretch',
            gap: attachments.length > 0 ? '6px' : '0px',
            padding: '6px 8px',
            borderRadius: attachments.length > 0 ? '22px' : '28px',
            // Width tracks the active state only, so clicking outside collapses the bar back
            // to its compact size — the staged attachments stay in place (nothing clears them).
            width: isBarActive ? '100%' : 'min(400px, 100%)',
            margin: '0 auto',
            // Keep the bar above the conversation panel (zIndex 40) so its controls — the
            // attach icon in particular — always receive clicks, never covered by the panel.
            zIndex: 45,
            transition: 'width 280ms cubic-bezier(0.16, 1, 0.3, 1)',
          }}
          onClick={() => {
            // Explicit click with a pending reply preview → open the full conversation.
            if (barReplyPreview) { openBarPanel(); return; }
            if (!isBarActive) textAreaRef.current?.focus();
          }}
        >
          {useFile && attachments.length > 0 && (
            <div
              style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', padding: '6px 4px 2px' }}
              // Keep the textarea focused (don't collapse) and don't let clicks here bubble to
              // the bar's focus handler — so the remove (✕) button works in both bar states.
              onMouseDown={(e) => e.preventDefault()}
              onClick={(e) => e.stopPropagation()}
            >
              {attachments.map((att, index) => (
                <AttachmentPreview
                  key={index}
                  file={att.file}
                  onRemove={() => handleRemoveAttachment(att.file.name)}
                  uploading={uploadingFiles.has(att.file.name)}
                  backgroundColor={secondaryColor}
                  textColor={textColor}
                  mutedTextColor={mutedTextColor}
                />
              ))}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '100%', minWidth: 0 }}>
            <textarea
              ref={textAreaRef}
              className="ga-textarea-nosb"
              style={{ ...textAreaStyle, padding: '10px 8px', paddingRight: '8px' }}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onFocus={handleBarFocus}
              onBlur={() => { if (!barFilePickRef.current) setBarFocused(false); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submitBarMessage();
                }
              }}
              placeholder={barPlaceholder}
              rows={1}
            />
            {useFile && (
              <>
                <button
                  type="button"
                  style={attachButtonStyle}
                  title="Attach"
                  // Prevent the mousedown from blurring the textarea — otherwise the bar
                  // collapses mid-click, the icon shifts, and the click never lands.
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={(e) => { e.stopPropagation(); handleBarAttachClick(); }}
                >
                  <Paperclip size={20} color={mutedTextColor} />
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
            {!(useAudio && inputValue.trim() === '' && attachments.length === 0) && (
              <button
                type="submit"
                style={{ ...sendButtonStyle, ...(isSendDisabled ? sendButtonDisabledStyle : {}) }}
                disabled={isSendDisabled}
                aria-label={t('buttons.send', 'Send')}
                // Keep the textarea focused (don't collapse the bar) when clicking send.
                onMouseDown={(e) => e.preventDefault()}
              >
                <ArrowUp size={18} strokeWidth={3} color="#ffffff" />
              </button>
            )}
            {useAudio && inputValue.trim() === '' && attachments.length === 0 && (
              <VoiceInput
                onAudioReady={async (blob: Blob, format: string) => {
                  openBarPanel();
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
        </form>

        {agentDisclaimerContent && (
          <div className="ga-input-disclaimer" style={{ ...disclaimerStyle, textAlign: 'center', margin: '8px 4px 0' }}>
            {agentDisclaimerContent}
          </div>
        )}
      </div>
    );
  };

  if (mode === 'inputbar') {
    return renderWithReCaptcha(renderInputBarComponent());
  }

  if (mode === 'floating') {
    const isPanelClosing = isPanelMounted && !isFloatingOpen;
    return (
      <>
        {/* Keyframes/animation classes must exist even while the panel is unmounted. */}
        <style>{CSS_KEYFRAMES}</style>
        {!isPanelMounted && (
          <BubbleDock
            primaryColor={primaryColor}
            position={position}
            offsetX={offsetX}
            offsetY={offsetY}
            windowWidth={windowWidth}
            placeholder={inputPlaceholder}
            fontFamily={fontFamily}
            fontSize={fontSize}
            inputBackgroundColor={inputBackgroundColor}
            borderColor={borderColor}
            textColor={textColor}
            chatBubbleIcon={theme?.chatBubbleIcon}
            showQuickInput={quickInput && !quickInputDismissed && Boolean(conversationId) && !isFinalized}
            unreadCount={unreadCount}
            onOpen={() => setIsFloatingOpen(true)}
            onSend={handleQuickInputSend}
            onDismissQuickInput={handleDismissQuickInput}
          />
        )}

        {isPanelMounted && (
          <div
            style={floatingContainerStyle}
            className={isPanelClosing ? 'ga-widget-out' : 'ga-widget-in'}
            onAnimationEnd={(e) => {
              // Ignore bubbled child animations; only react to the panel's own close.
              if (e.target !== e.currentTarget) return;
              if (isPanelClosing) setIsPanelMounted(false);
            }}
            data-genassist-container="floating"
          >
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
