import { describe, expect, it } from "vitest";
import type { AgentDailyStatsItem } from "@/interfaces/analyticsReports.interface";
import { aggregateAgentRows, toConversationCountsByAgent } from "./agentRows";

const dailyRow = (
  agent_id: string,
  overrides: Partial<AgentDailyStatsItem> = {},
): AgentDailyStatsItem => ({
  id: `${agent_id}-${overrides.stat_date ?? "2026-08-01"}`,
  agent_id,
  stat_date: "2026-08-01",
  execution_count: 10,
  success_count: 9,
  error_count: 1,
  avg_response_ms: 500,
  min_response_ms: 100,
  max_response_ms: 900,
  total_nodes_executed: 20,
  avg_success_rate: 0.9,
  rag_used_count: 2,
  unique_conversations: 4,
  finalized_conversations: 3,
  in_progress_conversations: 1,
  thumbs_up_count: 1,
  thumbs_down_count: 0,
  last_aggregated_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

const canonical = (
  agent_id: string,
  unique_conversations: number,
  finalized_conversations = unique_conversations,
  in_progress_conversations = 0,
) => ({
  agent_id,
  unique_conversations,
  finalized_conversations,
  in_progress_conversations,
});

describe("toConversationCountsByAgent", () => {
  it("returns null when the summary carried no rows", () => {
    expect(toConversationCountsByAgent(undefined)).toBeNull();
  });

  it("returns an empty map for an empty row list", () => {
    expect(toConversationCountsByAgent([])?.size).toBe(0);
  });
});

describe("aggregateAgentRows", () => {
  it("sums execution metrics across daily buckets", () => {
    const rows = aggregateAgentRows(
      [
        dailyRow("a", { execution_count: 10, success_count: 9, error_count: 1 }),
        dailyRow("a", { stat_date: "2026-08-02", execution_count: 5, success_count: 5, error_count: 0 }),
      ],
      null,
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].execution_count).toBe(15);
    expect(rows[0].success_count).toBe(14);
    expect(rows[0].error_count).toBe(1);
  });

  it("weights avg response time by execution count", () => {
    const rows = aggregateAgentRows(
      [
        dailyRow("a", { execution_count: 10, avg_response_ms: 100 }),
        dailyRow("a", { stat_date: "2026-08-02", execution_count: 30, avg_response_ms: 200 }),
      ],
      null,
    );
    expect(rows[0].avg_response_ms).toBe((10 * 100 + 30 * 200) / 40);
  });

  it("keeps daily conversation counts when no canonical rows exist", () => {
    const rows = aggregateAgentRows([dailyRow("a", { unique_conversations: 4 })], null);
    expect(rows[0].unique_conversations).toBe(4);
  });

  it("prefers canonical counts over the daily bucket count", () => {
    const rows = aggregateAgentRows(
      [dailyRow("a", { unique_conversations: 4 })],
      toConversationCountsByAgent([canonical("a", 2, 1, 1)]),
    );
    expect(rows[0].unique_conversations).toBe(2);
    expect(rows[0].finalized_conversations).toBe(1);
    expect(rows[0].in_progress_conversations).toBe(1);
  });

  it("zeroes an agent whose daily buckets fall outside the exact activity interval", () => {
    const rows = aggregateAgentRows(
      [dailyRow("a", { unique_conversations: 4 }), dailyRow("b", { unique_conversations: 7 })],
      toConversationCountsByAgent([canonical("a", 4)]),
    );
    const b = rows.find((row) => row.agent_id === "b")!;
    expect(b.unique_conversations).toBe(0);
    expect(b.execution_count).toBe(10);
  });

  it("adds a row for an agent that only the canonical counts know about", () => {
    const rows = aggregateAgentRows(
      [dailyRow("a", { unique_conversations: 4 })],
      toConversationCountsByAgent([canonical("a", 4), canonical("b", 3, 2, 1)]),
    );
    const b = rows.find((row) => row.agent_id === "b")!;
    expect(b).toMatchObject({
      agent_id: "b",
      unique_conversations: 3,
      finalized_conversations: 2,
      in_progress_conversations: 1,
      execution_count: 0,
      avg_response_ms: null,
    });
  });

  it("makes the rows sum to the canonical summary total", () => {
    const canonicalRows = [canonical("a", 4), canonical("b", 3), canonical("c", 5)];
    const summaryTotal = canonicalRows.reduce((sum, row) => sum + row.unique_conversations, 0);
    const rows = aggregateAgentRows(
      [
        dailyRow("a", { unique_conversations: 9 }),
        dailyRow("b", { unique_conversations: 1 }),
        dailyRow("d", { unique_conversations: 6 }),
      ],
      toConversationCountsByAgent(canonicalRows),
    );
    const rowTotal = rows.reduce((sum, row) => sum + row.unique_conversations, 0);
    expect(rowTotal).toBe(summaryTotal);
    expect(rows.map((row) => row.agent_id).sort()).toEqual(["a", "b", "c", "d"]);
  });
});
