export interface TranscriptEntry {
  speaker: string;
  text: string;
  start_time: number;
  end_time: number;
  create_time: string | number;
  type?: "message" | "takeover" | string;
  message_id?: string;
  feedback?: string | ConversationFeedbackEntry[] | null;
}

export interface Recording {
  id: string;
  file_path: string;
  data_source_id: number;
  operator_id: number;
  created_at: string;
  updated_at: string;
  recording_date: string;
}

export interface Analysis {
  conversation_id: number;
  topic: string;
  transcription: string;
  summary: string;
  negative_sentiment: number;
  positive_sentiment: number;
  neutral_sentiment: number;
  tone: string;
  customer_satisfaction: number;
  operator_knowledge: number;
  resolution_rate: number;
  llm_analyst_id: string;
  efficiency: number;
  response_time: number;
  quality_of_service: number;
}

export interface BackendTranscript {
  id: string;
  operator_id: string;
  data_source_id: string;
  recording_id: string | null;
  created_at: string;
  updated_at: string;
  conversation_date: string;
  transcription: string | TranscriptEntry[] | null;
  customer_id: number | string | null;
  thread_id?: string | null;
  word_count: number;
  customer_ratio: number;
  agent_ratio: number;
  duration: number;
  status: "finalized" | "in_progress" | "takeover" | string;
  conversation_type?: string;
  requires_supervisor?: boolean;
  in_progress_hostility_score: number;
  supervisor_id?: string | null;
  recording: Recording | null;
  analysis?: Analysis | null;
  topic?: string;
  negative_reason?: string;
  messages?: Array<
    Partial<TranscriptEntry> & {
      id?: string;
    }
  > | null;
  feedback?: string | ConversationFeedbackEntry[] | null;
}

export interface TranscriptMetrics {
  sentiment: string;
  customerSatisfaction: number;
  serviceQuality: number;
  resolutionRate: number;
  speakingRatio: {
    agent: number;
    customer: number;
  };
  tone: string[];
  wordCount: number;
  in_progress_hostility_score?: number;
  hostility?: number;
}

export interface TranscriptMetadata {
  isCall: boolean;
  duration: number;
  title: string;
  topic: string;
  customer_speaker?: string;
}

export interface ConversationFeedbackEntry {
  feedback: "good" | "bad";
  feedback_timestamp: string;
  feedback_user_id: string;
  feedback_message: string;
}

export interface Transcript {
  id: string;
  audio: string;
  duration: number;
  recording_id: string | null;
  timestamp: string;
  create_time: string;
  status?: string;
  transcription: TranscriptEntry[] | string | null;
  messages?: TranscriptEntry[];
  metadata: TranscriptMetadata;
  metrics: TranscriptMetrics;
  agent_ratio?: number;
  customer_ratio?: number;
  word_count?: number;
  in_progress_hostility_score?: number;
  supervisor_id?: string | null;
  feedback?: ConversationFeedbackEntry[];

  // NOTE: used to avoid parsing issues
  transcript?: TranscriptEntry[] | string | null;
}
