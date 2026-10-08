type MetricConfig = Record<string, unknown> | undefined;

// Plain names for the grading sources a metric can be checked against.
const SOURCE_LABELS: Record<string, string> = {
  none: "Rubric only",
  expected_output: "Expected reply",
  output: "The reply",
  kb_retrievals: "Retrieved context",
  conversation_context: "Conversation so far",
  tool_events: "Tool results",
};

// Older configs stored a run-data path instead of a source.
const LEGACY_FIELD_SOURCES: Record<string, string> = {
  reference_outputs: "expected_output",
  outputs: "output",
  "trace.retrievals": "kb_retrievals",
  "trace.session": "conversation_context",
  "trace.tool_events": "tool_events",
};

interface ResolvedSource {
  source: string | null;
  field: string | null;
}

const nonEmptyString = (value: unknown): string | null =>
  typeof value === "string" && value ? value : null;

// The saved source key wins, then the legacy field, then the backend's default.
const resolveSource = (
  config: MetricConfig,
  sourceKey: string,
  legacyKey: string,
  fallback: string,
): ResolvedSource => {
  const source = nonEmptyString(config?.[sourceKey]);
  if (source) return { source, field: null };
  const field = nonEmptyString(config?.[legacyKey]);
  if (field) return { source: LEGACY_FIELD_SOURCES[field] ?? null, field };
  return { source: fallback, field: null };
};

const sourceLabel = ({ source, field }: ResolvedSource): string => {
  if (source) return SOURCE_LABELS[source] ?? source;
  return `Run data: ${field}`;
};

// Each LLM judge rule has its own source; a legacy config is one rule.
const judgeSources = (config: MetricConfig): ResolvedSource[] => {
  if (!config) return [];
  const rules = Array.isArray(config.rules)
    ? config.rules.filter(
        (rule): rule is Record<string, unknown> => Boolean(rule) && typeof rule === "object",
      )
    : [config];
  return rules.map((rule) => resolveSource(rule, "source_type", "source_field", "none"));
};

const evidenceSource = (config: MetricConfig) =>
  resolveSource(config, "evidence_source", "evidence_field", "expected_output");

const contextSource = (config: MetricConfig) =>
  resolveSource(config, "context_source", "context_field", "expected_output");

// What a metric was graded against, for the "Checked against" line.
export const metricSourceLabel = (technique: string, config: MetricConfig): string | null => {
  switch (technique) {
    case "exact_match":
    case "contains":
    case "json_match":
      return SOURCE_LABELS.expected_output;
    case "not_contains": {
      const hasPhrases = Array.isArray(config?.phrases)
        ? (config.phrases as unknown[]).length > 0
        : Boolean(config?.text);
      return hasPhrases ? "Configured forbidden phrases" : "Forbidden phrases";
    }
    case "field_equals":
      return config?.expected !== undefined
        ? "Configured expected value"
        : SOURCE_LABELS.expected_output;
    case "nli_eval":
      return sourceLabel(evidenceSource(config));
    case "provenance_eval":
      return sourceLabel(contextSource(config));
    case "llm_judge": {
      const labels = [...new Set(judgeSources(config).map(sourceLabel))];
      return labels.length ? labels.join(", ") : SOURCE_LABELS.none;
    }
    default:
      return null;
  }
};

// True only when the metric grades against the test case's expected reply.
export const usesExpectedOutput = (technique: string, config: MetricConfig): boolean => {
  switch (technique) {
    case "exact_match":
    case "contains":
    case "json_match":
      return true;
    case "field_equals":
      return config?.expected === undefined;
    case "nli_eval":
      return evidenceSource(config).source === "expected_output";
    case "provenance_eval":
      return contextSource(config).source === "expected_output";
    case "llm_judge":
      return judgeSources(config).some((rule) => rule.source === "expected_output");
    default:
      return false;
  }
};

// "comment. Checked against: source", without doubling the comment's own full stop.
export const checkedAgainstLine = (
  comment: string | null | undefined,
  label: string,
): string => {
  const text = (comment ?? "").trim();
  if (!text) return `Checked against: ${label}`;
  const stop = /[.!?]$/.test(text) ? "" : ".";
  return `${text}${stop} Checked against: ${label}`;
};
