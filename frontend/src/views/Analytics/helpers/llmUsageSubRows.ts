import type { LlmUsageDimension } from "@/interfaces/llmUsage.interface";

export type SourceSubRowParent = "evaluation" | "llm_analyst";

interface SourceSubRowConfig {
  dimension: LlmUsageDimension;
  unit: [singular: string, plural: string];
  emptyText: string;
  errorText: string;
}

/** Usage types whose row expands into its own breakdown */
export const SOURCE_SUB_ROWS: Record<SourceSubRowParent, SourceSubRowConfig> = {
  evaluation: {
    dimension: "evaluation_method",
    unit: ["method", "methods"],
    emptyText: "No evaluation LLM spend in this period.",
    errorText: "Failed to load evaluation breakdown.",
  },
  llm_analyst: {
    dimension: "analyst_purpose",
    unit: ["analysis", "analyses"],
    emptyText: "No analyst LLM spend in this period.",
    errorText: "Failed to load analyst breakdown.",
  },
};

export const isSourceSubRowParent = (key: string): key is SourceSubRowParent =>
  Object.prototype.hasOwnProperty.call(SOURCE_SUB_ROWS, key);

export function subRowCountLabel(parent: SourceSubRowParent, count: number | undefined): string | null {
  if (!count) return null;
  const [singular, plural] = SOURCE_SUB_ROWS[parent].unit;
  return `${count} ${count === 1 ? singular : plural}`;
}
