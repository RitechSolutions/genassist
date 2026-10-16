import type { WorkflowMinimal } from "@/interfaces/workflow.interface";

/** A workflow row on the evaluations page, as far as its section needs it. */
export interface SectionRow {
  key: string;
  name: string;
}

export interface SectionPlan<Row extends SectionRow> {
  row: Row;
  /** The search a section applies to its evaluations: none when the workflow's name matched. */
  search: string;
  open: boolean;
  /** How many of its evaluations match, when it shows for them. */
  matches: number | null;
}

/** Which workflows show and which are open: folded unless opened (a lone one opens); a search shows its matches open. */
export const planSections = <Row extends SectionRow>(
  rows: Row[],
  query: string,
  /** Matching evaluations by workflow key, from one search; null until it answers. */
  matches: Map<string, number> | null,
  /** The workflows the person opened (true) or folded (false). */
  opened: Record<string, boolean>,
  foldedInSearch: Set<string>,
): { sections: SectionPlan<Row>[]; searching: boolean } => {
  const search = query.trim();
  const lowered = search.toLowerCase();
  if (!lowered) {
    const open = (key: string) => opened[key] ?? rows.length === 1;
    return { sections: rows.map((row) => ({ row, search: "", open: open(row.key), matches: null })), searching: false };
  }
  const sections: SectionPlan<Row>[] = [];
  for (const row of rows) {
    const nameMatches = row.name.toLowerCase().includes(lowered);
    const count = matches?.get(row.key) ?? 0;
    if (!nameMatches && !count) continue;
    sections.push({
      row,
      search: nameMatches ? "" : search,
      open: !foldedInSearch.has(row.key),
      matches: nameMatches ? null : count,
    });
  }
  return { sections, searching: matches === null };
};

/** The section of a workflow id; sections are keyed by the agent's live version, so older versions match by agent. */
export const sectionKeyFor = (
  workflowId: string,
  rows: { key: string; workflowId: string | null }[],
  workflows: Pick<WorkflowMinimal, "id" | "agent_id">[],
): string | null => {
  if (rows.some((row) => row.key === workflowId)) return workflowId;
  const agentOf = (id: string | null) => (id ? workflows.find((workflow) => workflow.id === id)?.agent_id ?? null : null);
  const agent = agentOf(workflowId);
  if (!agent) return null;
  return rows.find((row) => agentOf(row.workflowId) === agent)?.key ?? null;
};
