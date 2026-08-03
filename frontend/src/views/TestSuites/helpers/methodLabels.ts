// Friendly evaluation-method names shown everywhere in place of raw technique keys.
export const METHOD_LABELS: Record<string, string> = {
  exact_match: "Exact Match",
  contains: "Contains",
  not_contains: "Does Not Contain",
  json_match: "JSON Match",
  field_equals: "Field Equals",
  tool_used: "Tool Usage",
  route_taken: "Route Taken",
  action_taken: "Action Taken",
  no_errors: "No Errors",
  nli_eval: "NLI Evaluation",
  provenance_eval: "Provenance Evaluation",
  llm_judge: "LLM Judge",
};

export const methodLabel = (technique: string): string =>
  METHOD_LABELS[technique] ?? technique;
