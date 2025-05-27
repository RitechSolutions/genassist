export type Agent = {
  firstName: string;
  lastName: string;
  avatar?: string | null;
  created_at?: string;
  operator_statistics?: {
    positive?: number;
    neutral?: number;
    negative?: number;
    totalCallDuration?: string;
    score?: number;
    callCount?: number;
    avg_customer_satisfaction?: number;
    avg_resolution_rate?: number;
    avg_response_time?: number;
    avg_quality_of_service?: number;
  };
  latest_conversation_analysis?: {
    conversation_id?: number;
    topic?: string;
    transcription?: string;
    summary?: string;
    negative_sentiment?: number;
    positive_sentiment?: number;
    neutral_sentiment?: number;
    tone?: string;
    customer_satisfaction?: number;
    operator_knowledge?: number;
    resolution_rate?: number;
    efficiency?: number;
    response_time?: number;
    quality_of_service?: number;
    duration?: number;
    agent_ratio?: number;
    customer_ratio?: number;
    created_at?: string;
    in_progress_hostility_score?: number;
    word_count?: number;
    status?: string;
    analysis?: {
      conversation_id?: string;
      topic?: string;
      summary?: string;
      negative_sentiment?: number;
      positive_sentiment?: number;
      neutral_sentiment?: number;
      tone?: string;
      customer_satisfaction?: number;
      operator_knowledge?: number;
      resolution_rate?: number;
      efficiency?: number;
      response_time?: number;
      quality_of_service?: number;
      id?: string;
    };
    recording?: {
      id?: string;
      operator_id?: string;
      recording_date?: string;
      created_at?: string;
      updated_at?: string;
    };
  };
};

export interface AgentDetailsDialogProps {
  agent: Agent | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}
