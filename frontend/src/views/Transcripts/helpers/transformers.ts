import { getApiUrl } from "@/config/api";
import { BackendTranscript, Transcript, TranscriptEntry, ConversationFeedbackEntry } from "@/interfaces/transcript.interface";

export function processApiResponse(data: unknown): BackendTranscript[] {
  if (!data) return [];

  let recordingsArray: BackendTranscript[] = [];

  if (Array.isArray(data)) {
    recordingsArray = data as BackendTranscript[];
  } else if (typeof data === "object" && data !== null) {
    const dataObj = data as Record<string, unknown>;
    if (Array.isArray(dataObj.data)) {
      recordingsArray = dataObj.data as BackendTranscript[];
    } else if (Array.isArray(dataObj.recordings)) {
      recordingsArray = dataObj.recordings as BackendTranscript[];
    } else {
      recordingsArray = [data as BackendTranscript];
    }
  }

  return recordingsArray.map((transcript) => ({
    ...transcript,
    isCall: Boolean(transcript.recording),
  }));
}

const baseApiUrl = await getApiUrl();

export function transformTranscript(backendData: BackendTranscript): Transcript {
  try {
    if (!backendData) {
      throw new Error(`Invalid backend data: ${JSON.stringify(backendData)}`);
    }

    const analysis = backendData.analysis || {} as BackendTranscript['analysis'];

    const isCall = Boolean(backendData.recording && backendData.recording.file_path);

    let dominantSentiment: "positive" | "neutral" | "negative" = "neutral";
    const positiveSentiment = analysis.positive_sentiment || 0;
    const negativeSentiment = analysis.negative_sentiment || 0;
    const neutralSentiment = analysis.neutral_sentiment || 0;

    if (positiveSentiment > negativeSentiment && positiveSentiment > neutralSentiment) {
      dominantSentiment = "positive";
    } else if (negativeSentiment > positiveSentiment && negativeSentiment > neutralSentiment) {
      dominantSentiment = "negative";
    }

    let transcriptArray: TranscriptEntry[] = [];
    if (Array.isArray(backendData.messages)) {
      transcriptArray = backendData.messages.map((entry) => {
        let perMessageFeedback: ConversationFeedbackEntry[] | undefined = undefined;
        try {
          const f = (entry as unknown as { feedback?: unknown }).feedback;
          if (typeof f === "string") {
            const parsed = JSON.parse(f);
            if (Array.isArray(parsed)) perMessageFeedback = parsed as ConversationFeedbackEntry[];
          } else if (Array.isArray(f)) {
            perMessageFeedback = f as ConversationFeedbackEntry[];
          }
        } catch {}

        return {
          speaker: entry.speaker || "Unknown",
          start_time: entry.start_time || 0,
          end_time: entry.end_time || (entry.start_time || 0) + 0.01,
          text: entry.text || "",
          create_time: entry.create_time || new Date().toISOString(),
          message_id: (entry as { id?: string }).id,
          feedback: perMessageFeedback,
          type: (entry as { type?: string }).type || "message",
        } as TranscriptEntry;
      });
    } else {
      try {
        const t = backendData.transcription as unknown;
        if (typeof t === "string" && t.trim() !== "") {
          const parsed = JSON.parse(t);
          if (Array.isArray(parsed)) {
            transcriptArray = (parsed as Partial<TranscriptEntry>[]).map((entry) => ({
              speaker: entry.speaker || "Unknown",
              start_time: entry.start_time || 0,
              end_time: entry.end_time || (entry.start_time || 0) + 0.01,
              text: entry.text || "",
              create_time: entry.create_time || new Date().toISOString(),
              message_id: (entry as { message_id?: string }).message_id,
              feedback: entry.feedback,
              type: (entry as { type?: string }).type || "message",
            }));
          }
        } else if (Array.isArray(backendData.transcription)) {
          transcriptArray = (backendData.transcription as Partial<TranscriptEntry>[]).map((entry) => ({
            speaker: entry.speaker || "Unknown",
            start_time: entry.start_time || 0,
            end_time: entry.end_time || (entry.start_time || 0) + 0.01,
            text: entry.text || "",
            create_time: entry.create_time || new Date().toISOString(),
            message_id: (entry as { message_id?: string }).message_id,
            feedback: entry.feedback,
            type: (entry as { type?: string }).type || "message",
          }));
        }
      } catch (e) {
        transcriptArray = [];
      }
    }

    const lastEntry = transcriptArray.length > 0 ? transcriptArray[transcriptArray.length - 1] : null;
    const durationInSeconds = backendData.duration ?? (
      lastEntry && transcriptArray[0]
        ? lastEntry.start_time - transcriptArray[0].start_time
        : 0
    );
    const minutes = Math.floor(durationInSeconds / 60);
    const seconds = Math.floor(durationInSeconds % 60);
    const formattedDuration = `${minutes}:${seconds.toString().padStart(2, "0")}`;

    const toneArray = analysis.tone ? [analysis.tone] : ["neutral"];

    const audioUrl = isCall ? `${baseApiUrl}${backendData.recording?.file_path}` : "";

    // Parse feedback from backend as stringified JSON or array
    let feedbackArray: ConversationFeedbackEntry[] | undefined = undefined;
    try {
      if (backendData.feedback) {
        if (typeof backendData.feedback === "string") {
          const parsed = JSON.parse(backendData.feedback);
          if (Array.isArray(parsed)) feedbackArray = parsed as ConversationFeedbackEntry[];
        } else if (Array.isArray(backendData.feedback)) {
          feedbackArray = backendData.feedback as ConversationFeedbackEntry[];
        }
      }
    } catch (e) {
      feedbackArray = undefined;
    }

    return {
      id: backendData.id.toString(),
      audio: audioUrl,
      create_time: backendData.created_at || new Date().toISOString(),
      recording_id: backendData.recording_id,
      transcription: transcriptArray,
      duration: durationInSeconds,
      status: backendData.status || "unknown",
      timestamp: backendData.created_at || new Date().toISOString(),
      agent_ratio: backendData.agent_ratio,
      customer_ratio: backendData.customer_ratio,
      word_count: backendData.word_count,
      in_progress_hostility_score: backendData.in_progress_hostility_score,
      supervisor_id: backendData.supervisor_id,
      metadata: {
        isCall,
        duration: durationInSeconds,
        title: `Conversation ${backendData.id}`,
        topic: analysis.topic || "Unknown",
      },
      messages: transcriptArray,
      metrics: {
        sentiment: dominantSentiment,
        customerSatisfaction: analysis.customer_satisfaction || 0,
        serviceQuality: analysis.quality_of_service || 0,
        resolutionRate: analysis.resolution_rate || 0,
        speakingRatio: {
          agent: backendData.agent_ratio || 50,
          customer: backendData.customer_ratio || 50,
        },
        tone: toneArray,
        wordCount: backendData.word_count || transcriptArray.reduce((count, item) => count + (item.text?.split(/\s+/).length || 0), 0),
        in_progress_hostility_score: backendData.in_progress_hostility_score,
      },
      feedback: feedbackArray,
    };
  } catch (error) {
    return {
      id: "error",
      audio: "",
      create_time: new Date().toISOString(),
      recording_id: null,
      transcription: [],
      duration: 0,
      status: "unknown",
      timestamp: new Date().toISOString(),
      agent_ratio: 0,
      customer_ratio: 0,
      word_count: 0,
      in_progress_hostility_score: 0,
      supervisor_id: null,
      metadata: {
        isCall: false,
        duration: 0,
        title: "Error",
        topic: " - Unknown",
      },
      messages: [],
      metrics: {
        sentiment: "neutral",
        customerSatisfaction: 0,
        serviceQuality: 0,
        resolutionRate: 0,
        speakingRatio: {
          agent: 50,
          customer: 50,
        },
        tone: ["neutral"],
        wordCount: 0,
        in_progress_hostility_score: 0,
      },
    };
  }
}
