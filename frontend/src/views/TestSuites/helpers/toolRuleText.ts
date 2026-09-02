import type { ToolRuleResultDetails } from "@/interfaces/testEvaluation.interface";

export const times = (n: number): string => `${n} time${n === 1 ? "" : "s"}`;

const toolName = (details: ToolRuleResultDetails, id: string): string =>
  details.tools?.[id]?.label ?? id;

const listPhrase = (names: string[], conjunction: "and" | "or"): string => {
  if (names.length === 0) return "a tool";
  const quoted = names.map((name) => `"${name}"`);
  if (quoted.length === 1) return quoted[0];
  return `${quoted.slice(0, -1).join(", ")} ${conjunction} ${quoted[quoted.length - 1]}`;
};

// One-line "what the rule requires", derived from the stored rule snapshot.
export const toolExpectedText = (details: ToolRuleResultDetails): string => {
  const rule = details.rule ?? {};
  const operator = rule.operator ?? details.operator ?? "all";
  const ids = rule.tool_ids ?? Object.keys(details.tools ?? {});
  const names = ids.map((id) => toolName(details, id));

  if (operator === "none") return `Do not use ${listPhrase(names, "or")}.`;
  if (operator === "only") {
    return names.length ? `Use only ${listPhrase(names, "or")}.` : "Do not use any tools.";
  }

  const conjunction = operator === "all" ? "and" : "or";
  const successfully = rule.require_success ? " successfully" : "";
  const { min_calls: min, max_calls: max } = rule;
  let count = "at least once";
  if (min != null && max != null) count = `between ${min} and ${max} times`;
  else if (min != null) count = `at least ${times(min)}`;
  else if (max != null) count = `at most ${times(max)}`;
  return `Use ${listPhrase(names, conjunction)}${successfully} ${count}.`;
};

// One-line "what actually happened", from observed/missing/failed tools + counts.
export const toolActualText = (details: ToolRuleResultDetails, status: string): string => {
  if (status === "not_evaluated") {
    return details.comment ?? "This rule could not be checked.";
  }
  const counts = details.call_counts ?? {};
  const successful = details.successful_call_counts ?? {};
  const parts: string[] = [];

  for (const id of details.observed_tools ?? []) {
    const total = counts[id] ?? 0;
    const succeeded = successful[id] ?? 0;
    // Only say "successfully" when the calls actually succeeded (a rule without
    // require_success is satisfied even by a failed call).
    if (succeeded > 0 && succeeded === total) {
      parts.push(`Used "${toolName(details, id)}" successfully ${times(total)}`);
    } else {
      parts.push(`Called "${toolName(details, id)}" ${times(total)}; ${succeeded} succeeded`);
    }
  }
  for (const id of details.failed_tools ?? []) {
    parts.push(`"${toolName(details, id)}" was called ${times(counts[id] ?? 0)}, but did not succeed`);
  }
  for (const id of details.missing_tools ?? []) {
    parts.push(`"${toolName(details, id)}" was not called`);
  }
  for (const id of details.forbidden_tools ?? []) {
    parts.push(`"${toolName(details, id)}" was used ${times(counts[id] ?? 0)} (not allowed)`);
  }
  for (const [id, reason] of Object.entries(details.check_failures ?? {})) {
    parts.push(`"${toolName(details, id)}": ${reason}`);
  }

  if (parts.length === 0) {
    return details.comment ?? (status === "passed" ? "Expectation met." : "");
  }
  return `${parts.join(". ")}.`;
};

