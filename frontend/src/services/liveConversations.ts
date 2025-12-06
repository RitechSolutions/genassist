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

const parseEntriesFromBackend = (rec: BackendTranscript): TranscriptEntry[] => {
  if (Array.isArray(rec.messages)) {
    return rec.messages.map((entry: Partial<TranscriptEntry> & { id?: string }) => ({
      text: entry.text ?? "",
      speaker: entry.speaker ?? "Unknown",
      start_time: entry.start_time ?? 0,
      end_time: entry.end_time ?? (entry.start_time ?? 0) + 0.01,
      create_time: entry.create_time ?? new Date().toISOString(),
      type: entry.type ?? "message",
      message_id: (entry as { id?: string }).id,
      feedback: entry.feedback ?? [],
    }));
  }

  const transcription = rec.transcription as unknown;
  if (typeof transcription === "string" && transcription.trim() !== "") {
    try {
      const parsed = JSON.parse(transcription);
      if (Array.isArray(parsed)) {
        return (parsed as Partial<TranscriptEntry>[]).map((entry) => ({
          text: entry.text ?? "",
          speaker: entry.speaker ?? "Unknown",
          start_time: entry.start_time ?? 0,
          end_time: entry.end_time ?? (entry.start_time ?? 0) + 0.01,
          create_time: entry.create_time ?? new Date().toISOString(),
          type: (entry as { type?: string }).type ?? "message",
          message_id: (entry as { message_id?: string }).message_id,
          feedback: entry.feedback ?? [],
        }));
      }
    } catch {
      // ignore
    }
  }
  return [];
};

export const conversationService = {
  getCachedTopic: (id: string): string | null => {
    try {
      const v = localStorage.getItem(`conversation_topic:${id}`);
      return v && v !== "" ? v : null;
    } catch {
      return null;
    }
  },
  setCachedTopic: (id: string, topic: string | undefined | null): void => {
    try {
      if (typeof topic === "string" && topic.trim() !== "" && topic !== "Unknown") {
        localStorage.setItem(`conversation_topic:${id}`, topic);
      }
    } catch {
      // ignore
    }
  },
  removeCachedTopic: (id: string): void => {
    try {
      localStorage.removeItem(`conversation_topic:${id}`);
    } catch {
      // ignore
    }
  },
  fetchInProgressCount: async (): Promise<number> => {
    try {
      const response = await apiRequest<{ count: number } | number | null>(
        "get",
        "/conversations/filter/count?conversation_status=takeover&conversation_status=in_progress"
      );
      if (response === null || response === undefined) return 0;
      if (typeof response === "number") return response;
      if (typeof (response).count === "number") return (response).count;
      return 0;
    } catch (error) {
      return 0;
    }
  },
  fetchTranscript: async (id: string): Promise<ConversationTranscript> => {
    const response = await apiRequest<BackendTranscript>(
      "get",
      `/conversations/${id}`
    );
    const entries: TranscriptEntry[] = parseEntriesFromBackend(response);
    

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
    try {
      conversationService.setCachedTopic(response.id, topic);
    } catch {
      // ignore
    }

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

  fetchActive: async (options?: { fromDate?: string; toDate?: string; sentiment?: string; category?: string; hostility_neutral_max?: number | string; hostility_positive_max?: number | string; include_feedback?: boolean }): Promise<ActiveConversationsResponse> => {
    try {
      const params = new URLSearchParams();
      params.set("skip", "0");
      params.set("limit", "100");
      params.append("conversation_status", "in_progress");
      params.append("conversation_status", "takeover");

      if (options?.fromDate) params.append("from_date", options.fromDate);
      if (options?.toDate) params.append("to_date", options.toDate);
      const s = (options?.sentiment || "").toLowerCase();
      const c = options?.category || ""; // keep server enum casing
      if (s && s !== "all") {
        params.append("sentiment", s);
        if (options?.hostility_neutral_max !== undefined) {
          params.append("hostility_neutral_max", String(options.hostility_neutral_max));
        }
        if (options?.hostility_positive_max !== undefined) {
          params.append("hostility_positive_max", String(options.hostility_positive_max));
        }
      }
      if (c && c !== "all") params.append("conversation_topics", c);
      if (typeof options?.include_feedback === "boolean") params.append("include_feedback", String(options.include_feedback));

      const url = `/conversations/?${params.toString()}`;
      const raw = await apiRequest<unknown>("get", url);

      const normalizeApiList = (payload: unknown): BackendTranscript[] => {
        if (!payload) return [] as BackendTranscript[];
        if (Array.isArray(payload)) return payload as BackendTranscript[];
        const asObj = payload as Record<string, unknown>;
        if (Array.isArray(asObj.items)) return asObj.items as BackendTranscript[];
        if (Array.isArray(asObj.data)) return asObj.data as BackendTranscript[];
        if (Array.isArray((asObj as { conversations?: unknown[] }).conversations)) return (asObj as { conversations: unknown[] }).conversations as BackendTranscript[];
        return [] as BackendTranscript[];
      };

      const allConversations = normalizeApiList(raw);

      const conversations: ActiveConversation[] = allConversations
        .filter((rec) => rec.status === "in_progress" || rec.status === "takeover")
        .map((rec) => ({
          id: rec.id,
          type: rec.recording ? "call" : "chat",
          status: rec.status === "in_progress" ? "in-progress" : "takeover",
          transcript: parseEntriesFromBackend(rec),
          sentiment: "negative",
          timestamp: rec.created_at,
          in_progress_hostility_score: rec.in_progress_hostility_score || 0,
          duration: rec.duration,
          word_count: rec.word_count,
          agent_ratio: rec.agent_ratio,
          customer_ratio: rec.customer_ratio,
          supervisor_id: rec.supervisor_id,
          topic: rec.analysis?.topic || undefined,
          negative_reason:
            (rec as unknown as { negative_reason?: string }).negative_reason ||
            ((rec as unknown as { analysis?: { negative_reason?: string } })?.analysis?.negative_reason) ||
            undefined,
        }));

      // Apply cached topics and persist any provided topics
      const withTopics = conversations.map((conv) => {
        if (conv.topic && conv.topic !== "Unknown") {
          conversationService.setCachedTopic(conv.id, conv.topic);
          return conv;
        }
        const cached = conversationService.getCachedTopic(conv.id);
        return cached ? { ...conv, topic: cached } : conv;
      });

      return { total: withTopics.length, conversations: withTopics };
    } catch (error) {
      return { total: 0, conversations: [] };
    }
  },

  getCachedTranscript: (id: string): TranscriptEntry[] | null => {
    return null;
  }
};
