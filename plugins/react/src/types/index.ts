// Chat message types
export interface ChatMessage {
  create_time: number;
  start_time: number;
  end_time: number;
  speaker: 'customer' | 'agent';
  text: string;
}

// API Response types
export interface StartConversationResponse {
  message: string;
  conversation_id: string;
}

// Props for the GenAgentChat component
export interface GenAgentChatProps {
  baseUrl: string;
  apiKey: string;
  userData?: Record<string, any>; // For passing user information or other metadata
  onError?: (error: Error) => void;
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
} 