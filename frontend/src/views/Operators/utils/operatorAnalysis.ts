import { Operator } from "@/interfaces/operator.interface";
import { BackendTranscript } from "@/interfaces/transcript.interface";
import { parsePercentValue } from "@/helpers/formatters";

type LatestConversationAnalysis = NonNullable<Operator["latest_conversation_analysis"]>;

export function getLatestTranscript(transcripts: BackendTranscript[]): BackendTranscript | null {
  if (!transcripts.length) return null;

  const sortedTranscripts = [...transcripts].sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return sortedTranscripts[0] ?? null;
}

export function createConversationAnalysis(
  transcript: BackendTranscript,
  operator: Operator
): LatestConversationAnalysis {
  // avg_customer_satisfaction is a percent ("86.0%" / 86) on a 0-100 scale;
  // conversation-level satisfaction is on a 0-10 scale, hence the divide.
  const averagePercent = parsePercentValue(
    operator.operator_statistics?.avg_customer_satisfaction
  );
  const fallbackSatisfaction = averagePercent !== null ? averagePercent / 10 : 8.6;

  const customerSatisfaction =
    transcript.analysis?.customer_satisfaction ?? fallbackSatisfaction;

  return {
    duration: transcript.duration,
    created_at: transcript.created_at,
    agent_ratio: transcript.agent_ratio,
    customer_ratio: transcript.customer_ratio,
    analysis: {
      customer_satisfaction: customerSatisfaction,
    },
  };
}
