export { GenAgentChat } from './components/GenAgentChat';
export type { GenAgentChatProps, ChatMessage } from './types';
export { GenAgentConfigPanel } from './components/GenAgentConfigPanel';
export type {
  GenAgentConfigPanelProps,
  ChatTheme,
  ChatSettingsConfig,
  FeatureFlags,
} from './components/GenAgentConfigPanel';
export { ChatBubble } from './components/ChatBubble';
export { ChatService } from './services/chatService';
export { useChat } from './hooks/useChat';
export type { UseChatProps } from './hooks/useChat';
export type {
  Attachment,
  AgentWelcomeData,
  AgentThinkingConfig,
  ChatContentBlock,
  DynamicChatItem,
  ScheduleItem,
  Translations,
} from './types';
export {
  parseInteractiveContentBlocks,
  generateMessageContent,
} from './utils/interactiveContent';
export {
  defaultTranslations,
  spanishTranslations,
  frenchTranslations,
  germanTranslations,
  italianTranslations,
  portugueseTranslations,
  translationsByLanguage,
  getBrowserLanguage,
  getTranslation,
  getTranslationString,
  getTranslationArray,
  resolveLanguage,
  mergeTranslations,
  getTranslationsForLanguage,
} from './utils/i18n';
