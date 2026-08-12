import type {
  AgentConversationStatusByAgent,
  AgentDailyStatsItem,
} from "@/interfaces/analyticsReports.interface";

export interface AgentAggregated {
  id: string;
  agent_id: string;
  unique_conversations: number;
  finalized_conversations: number;
  in_progress_conversations: number;
  execution_count: number;
  success_count: number;
  error_count: number;
  avg_response_ms: number | null;
  total_nodes_executed: number;
  rag_used_count: number;
  thumbs_up_count: number;
  thumbs_down_count: number;
}

export type ConversationCounts = Pick<
  AgentAggregated,
  "unique_conversations" | "finalized_conversations" | "in_progress_conversations"
>;

type Accumulator = AgentAggregated & { _totalMs: number; _msCount: number };

const NO_CONVERSATIONS: ConversationCounts = {
  unique_conversations: 0,
  finalized_conversations: 0,
  in_progress_conversations: 0,
};

/** Canonical per-agent counts, or null when the summary carried none. */
export function toConversationCountsByAgent(
  rows: AgentConversationStatusByAgent[] | undefined,
): Map<string, ConversationCounts> | null {
  if (!rows) return null;
  return new Map(
    rows.map((row) => [
      row.agent_id,
      {
        unique_conversations: row.unique_conversations,
        finalized_conversations: row.finalized_conversations,
        in_progress_conversations: row.in_progress_conversations,
      },
    ]),
  );
}

function emptyRow(agentId: string): Accumulator {
  return {
    id: agentId,
    agent_id: agentId,
    ...NO_CONVERSATIONS,
    execution_count: 0,
    success_count: 0,
    error_count: 0,
    avg_response_ms: null,
    total_nodes_executed: 0,
    rag_used_count: 0,
    thumbs_up_count: 0,
    thumbs_down_count: 0,
    _totalMs: 0,
    _msCount: 0,
  };
}

/**
 * One row per agent: execution metrics from the UTC daily buckets, conversation
 * counts from the canonical rows when available (they cover the exact activity
 * window, not just whole UTC days). Canonical-only agents still get a row, so
 * totals keep matching the summary. No canonical rows → daily counts are used as-is.
 */
export function aggregateAgentRows(
  items: AgentDailyStatsItem[],
  conversationsByAgent: Map<string, ConversationCounts> | null,
): AgentAggregated[] {
  const map = new Map<string, Accumulator>();

  for (const item of items) {
    const existing = map.get(item.agent_id);
    if (existing) {
      existing.execution_count += item.execution_count;
      existing.success_count += item.success_count;
      existing.error_count += item.error_count;
      existing.total_nodes_executed += item.total_nodes_executed;
      existing.rag_used_count += item.rag_used_count;
      existing.thumbs_up_count += item.thumbs_up_count;
      existing.thumbs_down_count += item.thumbs_down_count;
      if (item.avg_response_ms != null) {
        existing._totalMs += item.avg_response_ms * item.execution_count;
        existing._msCount += item.execution_count;
      }
    } else {
      map.set(item.agent_id, {
        id: item.agent_id,
        agent_id: item.agent_id,
        unique_conversations: item.unique_conversations,
        finalized_conversations: item.finalized_conversations,
        in_progress_conversations: item.in_progress_conversations,
        execution_count: item.execution_count,
        success_count: item.success_count,
        error_count: item.error_count,
        avg_response_ms: item.avg_response_ms,
        total_nodes_executed: item.total_nodes_executed,
        rag_used_count: item.rag_used_count,
        thumbs_up_count: item.thumbs_up_count,
        thumbs_down_count: item.thumbs_down_count,
        _totalMs: item.avg_response_ms != null ? item.avg_response_ms * item.execution_count : 0,
        _msCount: item.avg_response_ms != null ? item.execution_count : 0,
      });
    }
  }

  for (const agentId of conversationsByAgent?.keys() ?? []) {
    if (!map.has(agentId)) map.set(agentId, emptyRow(agentId));
  }

  return Array.from(map.values()).map((row) => {
    const counts = conversationsByAgent
      ? (conversationsByAgent.get(row.agent_id) ?? NO_CONVERSATIONS)
      : row;
    return {
      ...row,
      unique_conversations: counts.unique_conversations,
      finalized_conversations: counts.finalized_conversations,
      in_progress_conversations: counts.in_progress_conversations,
      avg_response_ms: row._msCount > 0 ? row._totalMs / row._msCount : null,
    };
  });
}
