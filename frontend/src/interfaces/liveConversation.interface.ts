export type ActiveConversation = {
    id: string;
    type: "all" | "call" | "chat";
    status: "in-progress";
    transcript: string;
    sentiment: "positive" | "neutral" | "negative";
    timestamp: string;
    in_progress_hostility_score: number;
  };
  
  export type ActiveConversationsResponse = {
    total: number;
    conversations: ActiveConversation[];
  };
  
  export type ConversationTranscript = {
    id: string;
    audio: string;
    duration: string;
    metadata: {
      isCall: boolean;
      duration: string;
      title: string;
      topic: string;
    };
    transcript: Array<{
      speaker: string;
      text: string;
      start_time: number;
    }>;
    metrics: {
      sentiment: "positive" | "neutral" | "negative";
      customerSatisfaction: number;
      serviceQuality: number;
      resolutionRate: number;
      speakingRatio: {
        agent: number;
        customer: number;
      };
      tone: string[];
      wordCount: number;
    };
  };

  