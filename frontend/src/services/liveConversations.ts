import { apiRequest } from "@/config/api";
import {
  ActiveConversationsResponse,
  ConversationTranscript,
  ActiveConversation,
} from "@/interfaces/liveConversation.interface";
import {
  BackendTranscript,
  TranscriptEntry,
} from "@/interfaces/transcript.interface";
import { DEFAULT_LLM_ANALYST_ID } from "@/constants/llmModels";

const parseTranscript = (transcription: string): string => {
  try {
    const parsed = JSON.parse(transcription);
    
    if (Array.isArray(parsed)) {
      return transcription;
    }
  } catch {
    // If JSON.parse fails, it's not a JSON string, return as is (it might be plain text).
  }
  return transcription || "Transcript unavailable";
};

export const conversationService = {
  fetchTranscript: async (id: string): Promise<ConversationTranscript> => {
    const response = await apiRequest<BackendTranscript>(
      "get",
      `/conversations/${id}`
    );

    const rawEntries = JSON.parse(response.transcription || "[]");

    const entries: TranscriptEntry[] = rawEntries.map((entry: Partial<TranscriptEntry>): TranscriptEntry => ({
      text: entry.text ?? "",
      speaker: entry.speaker ?? "Unknown",
      start_time: entry.start_time ?? 0,
      end_time: entry.end_time ?? (entry.start_time ?? 0) + 1,
      create_time: entry.create_time ?? new Date().toISOString(),
    }));
    

    const analysis = response.analysis || {
      neutral_sentiment: 0,
      positive_sentiment: 0,
      negative_sentiment: 0,
      tone: "neutral",
      customer_satisfaction: 0,
      resolution_rate: 0,
      quality_of_service: 0,
    };

    const topic = response.analysis?.topic ?? "Unknown";

    let dominantSentiment: "positive" | "neutral" | "negative" = "neutral";
    const { neutral_sentiment, positive_sentiment, negative_sentiment } =
      analysis;

    if (
      positive_sentiment > neutral_sentiment &&
      positive_sentiment > negative_sentiment
    ) {
      dominantSentiment = "positive";
    } else if (
      negative_sentiment > positive_sentiment &&
      negative_sentiment > neutral_sentiment
    ) {
      dominantSentiment = "negative";
    }

    return {
      id: response.id,
      audio: response.recording?.file_path ?? "",
      duration: `${Math.floor(response.duration / 60)}m ${
        response.duration % 60
      }s`,
      metadata: {
        isCall: !!response.recording,
        duration: `${Math.floor(response.duration / 60)}m ${
          response.duration % 60
        }s`,
        title: `Call #${response.id.slice(-4)}`,
        topic,
      },
      transcript: entries,
      metrics: {
        sentiment: dominantSentiment,
        customerSatisfaction: analysis.customer_satisfaction ?? 0,
        serviceQuality: analysis.quality_of_service ?? 0,
        resolutionRate: analysis.resolution_rate ?? 0,
        speakingRatio: {
          agent: response.agent_ratio ?? 50,
          customer: response.customer_ratio ?? 50,
        },
        tone: [analysis.tone ?? "neutral"],
        wordCount: response.word_count ?? 0,
      },
    };
  },

  takeoverConversation: async (id: string): Promise<boolean> => {
    try {
      await apiRequest("patch", `conversations/in-progress/takeover-super/${id}`);
      return true;
    } catch (error) {
      console.error("Supervisor takeover failed:", error);
      return false;
    }
  },

  updateConversation: async (
    id: string,
    data: { messages: TranscriptEntry[]; llm_analyst_id: string }
  ): Promise<void> => {
    await apiRequest("patch", `/conversations/in-progress/update/${id}`, data);
  },

  finalizeConversation: async (id: string): Promise<void> => {
    await apiRequest("patch", `/conversations/in-progress/finalize/${id}`, {
      llm_analyst_id: DEFAULT_LLM_ANALYST_ID,
    });
  },    

  fetchActive: async (options?: { fromDate?: string; toDate?: string }): Promise<ActiveConversationsResponse> => {
    const fetchByStatus = async (status: string) => {
      const params = new URLSearchParams({
        skip: "0",
        limit: "50",
        conversation_status: status,
        minimum_hostility_score: "10",
      });
      
      if (options?.fromDate) {
        params.append("from_date", options.fromDate);
        console.log(`Using from_date: ${options.fromDate}`);
      }
      
      if (options?.toDate) {
        params.append("to_date", options.toDate);
        console.log(`Using to_date: ${options.toDate}`);
      }
      
      const url = `/conversations/?${params.toString()}`;
      console.log(`Fetching conversations with URL: ${url}`);
  
      return await apiRequest<BackendTranscript[]>("get", url);
    };
  
    try {
      const [inProgress, supervisorInProgress] = await Promise.all([
        fetchByStatus("in_progress"),
        fetchByStatus("takeover"),
      ]);
      
      console.log("Received conversations:", { 
        inProgress: inProgress?.length ?? 0,
        supervisorInProgress: supervisorInProgress?.length ?? 0
      });
    
      const allConversations = [...(inProgress ?? []), ...(supervisorInProgress ?? [])];
    
      const conversations: ActiveConversation[] = allConversations
      .filter(rec => rec.status === "in_progress" || rec.status === "takeover")
      .map((rec) => {
        return {
          id: rec.id,
          type: rec.recording ? "call" : "chat",
          status: rec.status as "in_progress" | "takeover",
          transcript: parseTranscript(rec.transcription),
          sentiment: "negative",
          timestamp: rec.created_at,
          in_progress_hostility_score: rec.in_progress_hostility_score || 0,
          duration: rec.duration,
          word_count: rec.word_count,
          agent_ratio: rec.agent_ratio,
          customer_ratio: rec.customer_ratio,
        };
      });
      
      console.log(`Returning ${conversations.length} conversations after filtering`);
    
      return {
        total: conversations.length,
        conversations,
      };
    } catch (error) {
      console.error("Error fetching active conversations:", error);
      return {
        total: 0,
        conversations: [],
      };
    }
  },

  getCachedTranscript: (id: string): TranscriptEntry[] | null => {
    return null;
  }
};
