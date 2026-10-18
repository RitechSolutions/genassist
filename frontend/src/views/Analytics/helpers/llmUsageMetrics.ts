import type { LlmUsageBreakdownItem } from "@/interfaces/llmUsage.interface";

export function pricedCostPerCall(
  item: Pick<LlmUsageBreakdownItem, "cost_usd" | "calls" | "unpriced_calls">
): number | null {
  const priced = item.calls - item.unpriced_calls;
  return priced > 0 ? item.cost_usd / priced : null;
}
