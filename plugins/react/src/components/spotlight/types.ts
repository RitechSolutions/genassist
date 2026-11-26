import type React from 'react';
import type { KeyboardViewport } from '../../hooks/useKeyboardViewport';
import type {
  AllowedExtension,
  AttachmentWithFile,
  ChatMessage,
  GenAgentChatProps,
  MessageReceiptStatus,
  ScheduleItem,
  Translations,
} from '../../types';
import type { ThemeParams } from '../../styles/genAgentChatStyles';
import type { LiveTurnLike } from './conversationItems';
import type { LiveVoiceStatus } from '../../hooks/useLiveVoice';


/**
 * Everything the spotlight UI needs from GenAgentChat. GenAgentChat stays the single
 * owner of chat state, connection, forms, voice and attachments; spotlight is purely a
 * presentation over it, so all modes keep identical behaviour.
 */
export interface SpotlightController {
  // ----- Presentation config -----
  theme: GenAgentChatProps['theme'];
  themeParams: ThemeParams;
  headerTitle: string;
  headerDescription: string;
  logoSrc: string;
  brandLogo: string;
  agentName?: string;
  inputPlaceholder: string;
  translations: Translations;
  t: (key: string, fallback?: string) => string;
  language: string;
  useFile: boolean;
  useAudio: boolean;
  allowedExtensions: AllowedExtension[];
  formDisplay: 'inline' | 'footer';
  showWelcomeBeforeStart: boolean;
  chatBubbleIcon?: 'message' | 'sparkles' | 'x';
  showPoweredBy: boolean;

  // ----- Viewport / panel -----
  position: string;
  offsetX: number;
  offsetY: number;
  windowWidth: number;
  windowHeight: number;
  isFullscreen: boolean;
  isExpanded: boolean;
  /** The on-screen keyboard while a chat field has focus (closed otherwise). */
  keyboard: KeyboardViewport;
  onExpandToggle: () => void;
  onFullscreenToggle: () => void;
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  isPanelMounted: boolean;
  onPanelClosed: () => void;

  // ----- Launcher -----
  showQuickInput: boolean;
  unreadCount: number;
  onQuickInputSend: (text: string) => void;
  onDismissQuickInput: () => void;

  // ----- Conversation state -----
  messages: ChatMessage[];
  isLoading: boolean;
  conversationId: string | null;
  isFinalized: boolean;
  isAgentTyping: boolean;
  isRestoringConversation: boolean;
  possibleQueries: string[];
  welcomeTitle?: string | null;
  welcomeImageUrl?: string | null;
  welcomeMessage?: string | null;
  hasUserMessages: boolean;
  shouldTriggerStartForm: boolean;
  disclaimerHtml?: string | null;
  /** Smooth-revealed text of the reply currently streaming ('' when none). */
  liveText: string;
  streamingCreateTime?: number;
  revealingMessage: ChatMessage | null;
  revealedText: string;
  /** The agent's own "Thinking Phrases" label while it works. Undefined when the agent has
   *  none configured — spotlight then shows typing dots instead of built-in phrases. */
  customThinkingLabel?: string;
  dividerBeforeKey: string | null;
  lastCustomerReceipt?: MessageReceiptStatus;
  latestQuestion?: ChatMessage;
  lastCustomerIndex: number;
  /** Show the composer's emoji button (spotlight only). */
  showEmojiPicker: boolean;
  /** Whether a failed message can be resent, and resending it. */
  canRetry: (message: ChatMessage) => boolean;
  onRetry: (message: ChatMessage) => void;

  // ----- Forms -----
  isFormAnswered: (originalIndex: number) => boolean;
  parseForm: (message: ChatMessage) => { message?: string; [k: string]: unknown } | null;
  pendingForm: { schema: any; index: number } | null;
  hasPendingForm: boolean;
  submittingFormIndex: number | null;
  onFormSubmit: (data: Record<string, unknown>, index: number) => void;
  onFormCancel: (index: number) => void;

  // ----- Composer -----
  inputValue: string;
  setInputValue: (v: string) => void;
  textAreaRef: React.RefObject<HTMLTextAreaElement>;
  onSubmit: () => void;
  isSendDisabled: boolean;
  shouldShowStartButton: boolean;
  onStartConversation: () => void;

  // ----- Actions -----
  onQueryClick: (query: string) => void;
  onQuickAction: (text: string) => void;
  onScheduleConfirm: (schedule: ScheduleItem) => void;
  onFeedback: (messageId: string, value: 'good' | 'bad') => void;

  // ----- Audio -----
  onSendAudio: (blob: Blob, format: string) => Promise<void>;
  onVoiceError: (error: Error) => void;
  audioUrlBuilder: (messageId: string) => string;
  audioHeaders: Record<string, string>;
  autoPlayAudioMessageId: string | null;

  // ----- Attachments -----
  attachments: AttachmentWithFile[];
  uploadingFiles: Set<string>;
  fileErrorToast: string | null;
  fileInputRef: React.RefObject<HTMLInputElement>;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  /** Attach and upload files that did not come from the file input (a screenshot). */
  onAddFiles: (files: File[]) => void;
  /** Show a short error under the composer. */
  onFileError: (message: string) => void;
  /** Offer "Add screenshot" in the + menu (spotlight only; needs useFile and a supporting browser). */
  allowScreenshot: boolean;
  onRemoveAttachment: (fileName: string) => void;

  // ----- Live voice -----
  liveVoiceEnabled: boolean;
  liveVoiceReady: boolean;
  liveVoiceStatus: LiveVoiceStatus;
  liveVoiceActive: boolean;
  onStartLiveCall: () => void;
  onEndLiveCall: () => void;
  liveTurns: LiveTurnLike[];
  liveCaption: LiveTurnLike;
  liveVoiceNotice: string | null;
  agentId?: string | null;

  // ----- Menu / language / reset -----
  showMenu: boolean;
  setShowMenu: (v: boolean) => void;
  showLanguageDropdown: boolean;
  setShowLanguageDropdown: (v: boolean) => void;
  languages: Array<{ code: string; name: string }>;
  onLanguageChange: (code: string) => void;
  /** The pre-conversation language picker, when it should show. */
  languageSelector: React.ReactNode;
  showResetConfirm: boolean;
  onResetClick: () => void;
  onConfirmReset: () => void;
  onCancelReset: () => void;

  // ----- Scroll -----
  chatContainerRef: React.RefObject<HTMLDivElement>;
  spacerRef: React.RefObject<HTMLDivElement>;
  setBottomSentinelRef: (el: HTMLDivElement | null) => void;
  showScrollButton: boolean;
  scrollToLatest: () => void;
}
