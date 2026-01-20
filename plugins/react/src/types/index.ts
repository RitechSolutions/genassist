import { Translations } from '../utils/i18n';

// Chat message types
export interface MessageFeedback {
  feedback: "good" | "bad";
  feedback_timestamp?: string;
  feedback_user_id?: string;
  feedback_message?: string;
}

export interface ChatMessage {
  create_time: number;
  start_time: number;
  end_time: number;
  speaker: "customer" | "agent" | "special";
  text: string;
  attachments?: Attachment[];
  // Optional metadata
  message_id?: string;
  feedback?: MessageFeedback[];
}

// Attachment type
export interface Attachment {
  name: string;
  type: string;
  size: number;
  url: string;
}

// API Response types
export interface StartConversationResponse {
  message: string;
  conversation_id: string;
  agent_welcome_message?: string;
  agent_possible_queries?: string[];
  agent_welcome_title?: string;
  agent_welcome_image_url?: string;
  agent_id?: string;
  agent_thinking_phrases?: string[];
  agent_thinking_phrase_delay?: number; // seconds
  create_time?: number;
  guest_token?: string;
}

// Agent welcome/config info
export interface AgentWelcomeData {
  title?: string | null;
  message?: string | null;
  imageUrl?: string | null;
  possibleQueries?: string[];
}

export interface AgentThinkingConfig {
  phrases: string[];
  delayMs: number; // rotation delay in ms
}

// Interactive content types
export interface DynamicChatItem {
  id: string;
  image?: string;
  type?: string;
  category?: string;
  name: string;
  description?: string;
  venueId?: string;
  slots?: string[];
  selectedSlot?: string;
}

export interface ScheduleItem {
  id: string;
  title?: string | null;
  restaurants: DynamicChatItem[];
}

export type ChatContentBlock =
  | { kind: "text"; text: string }
  | { kind: "items"; items: DynamicChatItem[] }
  | { kind: "schedule"; schedule: ScheduleItem }
  | { kind: "options"; options: string[] };

// Props for the GenAgentChat component
export interface GenAgentChatProps {
  baseUrl: string;
  apiKey: string;
  tenant: string | undefined;
  metadata?: Record<string, any>; // For passing user information or other metadata
  onError?: (error: Error) => void;
  onTakeover?: () => void;
  onFinalize?: () => void;
  theme?: {
    primaryColor?: string;
    secondaryColor?: string;
    fontFamily?: string;
    fontSize?: string;
    backgroundColor?: string;
    textColor?: string;
  };
  headerTitle?: string;
  placeholder?: string;
  agentName?: string; // Custom agent name to display instead of "Agent"
  logoUrl?: string; // Custom logo URL to display in header instead of default logo
  mode?: "embedded" | "floating";
  floatingConfig?: {
    position?: "bottom-right" | "bottom-left" | "top-right" | "top-left";
    offset?: { x?: number; y?: number };
    toggleButtonIcon?: React.ReactElement;
    closeButtonIcon?: React.ReactElement;
  };
  language?: string; // Language code (e.g., 'en', 'es', 'fr'). If not provided, will use browser language
  translations?: Partial<Translations>; // Custom translations. If not provided, will use default English translations
}

export type { Translations } from '../utils/i18n';
