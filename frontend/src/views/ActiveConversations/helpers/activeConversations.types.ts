import type { ActiveConversation } from "@/interfaces/liveConversation.interface";

export type EffectiveSentiment = "positive" | "neutral" | "negative";

export interface NormalizedConversation extends ActiveConversation {
  idx: number;
  effectiveSentiment: EffectiveSentiment;
}

export type SentimentFilter = "all" | "good" | "neutral" | "bad";