import {
  GuardrailCheckSettings,
  GuardrailPolicy,
  GuardrailStage,
  GuardrailVerdict,
  HarmCategory,
  HarmfulContent,
  UntrustedContentMode,
} from "@/interfaces/guardrails.interface";

export const HARM_CATEGORIES: { key: HarmCategory; label: string }[] = [
  { key: "hate", label: "Hate" },
  { key: "insults", label: "Insults" },
  { key: "sexual", label: "Sexual" },
  { key: "violence", label: "Violence" },
  { key: "self_harm", label: "Self-harm" },
  { key: "misconduct", label: "Misconduct" },
];

export const DEFAULT_BLOCKED_MESSAGE = "Sorry, I can't help with that.";

export const defaultGuardrailPolicy = (): GuardrailPolicy => ({
  mode: "off",
  judge_provider_id: null,
  prompt_attack: "off",
  harmful_content: Object.fromEntries(
    HARM_CATEGORIES.map(({ key }) => [key, "off"])
  ) as HarmfulContent,
  denied_topics: [],
  blocked_words: [],
  check_replies: false,
  untrusted_content: "off",
  blocked_message: DEFAULT_BLOCKED_MESSAGE,
});

export const usesJudge = (
  settings: GuardrailCheckSettings,
  untrustedContent: UntrustedContentMode = "off"
): boolean =>
  settings.prompt_attack !== "off" ||
  Object.values(settings.harmful_content).some((level) => level !== "off") ||
  settings.denied_topics.length > 0 ||
  untrustedContent !== "off";

const CHECK_LABELS: Record<string, string> = {
  blocked_words: "Blocked word",
  too_long: "Too long to check",
  prompt_attack: "Prompt attack",
  harmful_content: "Harmful content",
  denied_topic: "Denied topic",
  untrusted_content: "Hidden instructions",
  provider_refusal: "Provider refusal",
  grounding: "Grounding",
  malformed_verdict: "No clear verdict",
  detector_error: "Check failed",
};

const HARM_LABELS: Record<string, string> = Object.fromEntries(
  HARM_CATEGORIES.map(({ key, label }) => [key, label])
);

export const guardrailCheckLabel = ({
  check_type,
  category,
}: Pick<GuardrailVerdict, "check_type"> & {
  category?: string | null;
}): string => {
  const label = CHECK_LABELS[check_type] ?? check_type;
  if (!category) return label;
  if (check_type === "harmful_content") {
    return `${label}: ${HARM_LABELS[category] ?? category}`;
  }
  if (check_type === "denied_topic" || check_type === "blocked_words") {
    return `${label}: ${category}`;
  }
  return label;
};

const STAGE_LABELS: Record<GuardrailStage, string> = {
  input: "Message",
  output: "Reply",
  tool: "Tool result",
  node: "Node",
};

export const guardrailStageLabel = (stage: string): string =>
  STAGE_LABELS[stage as GuardrailStage] ?? stage;
