import {
  GuardrailCheckSettings,
  GuardrailEvent,
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

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isVerdict = (value: unknown): value is GuardrailVerdict =>
  isRecord(value) &&
  typeof value.check_type === "string" &&
  typeof value.action === "string";

export const extractGuardrailChecks = (parsed: unknown): GuardrailVerdict[] => {
  if (!isRecord(parsed)) return [];
  const row = isRecord(parsed.row_agent_response)
    ? parsed.row_agent_response.guardrail_events
    : undefined;
  const events = Array.isArray(row) ? row : parsed.guardrail_events;
  return Array.isArray(events) ? events.filter(isVerdict) : [];
};

export type GuardrailChip = "blocked" | "flagged";

export const guardrailChipsByMessage = (
  events: GuardrailEvent[]
): Record<string, GuardrailChip> => {
  const chips: Record<string, GuardrailChip> = {};
  for (const { transcript_message_id: id, action } of events) {
    if (!id || (action !== "blocked" && action !== "flagged")) continue;
    if (chips[id] !== "blocked") chips[id] = action;
  }
  return chips;
};
