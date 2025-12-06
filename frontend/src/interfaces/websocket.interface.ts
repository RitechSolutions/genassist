import { TranscriptEntry } from "./transcript.interface";
import { ActiveConversation, ActiveConversationsResponse } from "./liveConversation.interface";

export interface UseWebSocketTranscriptOptions {
    conversationId: string;
    token: string;
    transcriptInitial?: TranscriptEntry[];
  }
  
export interface StatisticsPayload {
    in_progress_hostility_score?: number;
    topic?: string;
    sentiment?: string;
    [key: string]: number | string | undefined;
  }
  
export interface TakeoverPayload {
    supervisor_id?: string;
    user_id?: string;
    timestamp?: string;
  }

// New interfaces for dashboard WebSocket
export interface UseWebSocketDashboardOptions {
    token: string;
    lang?: string;
    topics?: string[];
}

export interface DashboardWebSocketMessage {
    topic: "message" | "statistics" | "finalize" | "hostile" | "conversation_list" | "conversation_update" | "update" | "takeover";
    type?: "message" | "statistics" | "finalize" | "hostile" | "conversation_list" | "conversation_update" | "update" | "takeover";
    payload: ConversationListPayload | ConversationUpdatePayload | StatisticsPayload | ConversationDataPayload | TakeoverPayload | FinalizePayload | Record<string, unknown>;
}

export interface ConversationListPayload {
    conversations: ActiveConversation[];
    total: number;
}

export interface ConversationUpdatePayload {
    conversation: ActiveConversation;
    action: "added" | "updated" | "removed";
}

export interface ConversationDataPayload {
    conversation_id: string;
    in_progress_hostility_score?: number;
    transcript?: string | TranscriptEntry[];
    messages?: TranscriptEntry[];
    create_time?: string;
    duration?: number;
    word_count?: number;
    agent_ratio?: number;
    customer_ratio?: number;
    supervisor_id?: string;
    topic?: string;
    negative_reason?: string;
    [key: string]: unknown;
}

export interface FinalizePayload {
    conversation_id?: string;
    id?: string;
    status?: string;
    finalized_at?: string;
    [key: string]: unknown;
}
