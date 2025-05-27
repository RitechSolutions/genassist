import { Agent } from "@/interfaces/agent.interface";
import { BackendTranscript } from "@/interfaces/transcript.interface";

type LatestConversationAnalysis = NonNullable<Agent["latest_conversation_analysis"]>;

export function getLatestTranscript(transcripts: BackendTranscript[]): BackendTranscript | null {
  if (!transcripts.length) return null;

  const sortedTranscripts = [...transcripts].sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return sortedTranscripts[0] ?? null;
}

export function createConversationAnalysis(
  transcript: BackendTranscript,
  agent: Agent
): LatestConversationAnalysis {
  const fallbackSatisfaction =
    agent.operator_statistics?.avg_customer_satisfaction != null
      ? agent.operator_statistics.avg_customer_satisfaction / 10
      : 8.6;

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
