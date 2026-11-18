export type GuardrailMode = "off" | "detect" | "block";

export type Sensitivity = "off" | "low" | "medium" | "high";

export type HarmCategory =
  | "hate"
  | "insults"
  | "sexual"
  | "violence"
  | "self_harm"
  | "misconduct";

export type HarmfulContent = Record<HarmCategory, Sensitivity>;

export type UntrustedContentMode = "off" | "flag" | "block";

export interface DeniedTopic {
  name: string;
  definition: string;
  examples: string[];
}

export interface GuardrailCheckSettings {
  prompt_attack: Sensitivity;
  harmful_content: HarmfulContent;
  denied_topics: DeniedTopic[];
  blocked_words: string[];
}

export interface GuardrailPolicy extends GuardrailCheckSettings {
  mode: GuardrailMode;
  judge_provider_id: string | null;
  check_replies: boolean;
  untrusted_content: UntrustedContentMode;
  blocked_message: string;
}

export type GuardrailStage = "input" | "output" | "tool" | "node";

export type GuardrailAction =
  | "passed"
  | "flagged"
  | "blocked"
  | "error"
  | "skipped";

export interface GuardrailVerdict {
  stage: GuardrailStage;
  check_type: string;
  category: string | null;
  detector: string;
  score: number | null;
  mode: string;
  action: GuardrailAction;
  source: string | null;
}

export interface GuardrailEvent extends GuardrailVerdict {
  id: string;
  transcript_message_id: string | null;
  created_at: string;
}

export interface GuardrailCheckResponse {
  blocked: boolean;
  verdicts: GuardrailVerdict[];
}
