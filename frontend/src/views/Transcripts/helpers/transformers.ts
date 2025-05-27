import { getApiUrl } from "@/config/api";
import { BackendTranscript, Transcript, TranscriptEntry } from "@/interfaces/transcript.interface";

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
    try {
      transcriptArray = typeof backendData.transcription === "string"
        ? JSON.parse(backendData.transcription)
        : (Array.isArray(backendData.transcription) ? backendData.transcription : []);
    } catch (e) {
      console.error("Failed to parse transcription:", e);
      transcriptArray = [];
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

    return {
      id: backendData.id.toString(),
      audio: audioUrl,
      create_time: backendData.created_at || new Date().toISOString(),
      recording_id: backendData.recording_id,
      transcription: transcriptArray,
      duration: durationInSeconds,
      status: backendData.status || "unknown",
      timestamp: backendData.created_at || new Date().toISOString(),
      metadata: {
        isCall,
        duration: durationInSeconds,
        title: `Conversation ${backendData.id}`,
        topic: analysis.topic || " - Unknown",
      },
      transcript: transcriptArray.map(entry => ({
        speaker: entry.speaker || "Unknown",
        start_time: entry.start_time || 0,
        end_time: entry.end_time || (entry.start_time || 0) + 1,
        text: entry.text || "",
        create_time: entry.create_time || new Date().toISOString(),
      })),
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
      },
    };
  } catch (error) {
    console.error("Error in transformTranscript:", error);
    return {
      id: "error",
      audio: "",
      create_time: new Date().toISOString(),
      recording_id: null,
      transcription: [],
      duration: 0,
      status: "unknown",
      timestamp: new Date().toISOString(),
      metadata: {
        isCall: false,
        duration: "0:00",
        title: "Error",
        topic: " - Unknown",
      },
      transcript: [],
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
      },
    };
  }
}
