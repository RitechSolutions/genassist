import { WorkflowMinimal } from "@/interfaces/workflow.interface";

/** Compare version strings numerically ("10" > "9", "1.2" > "1.1"), tolerating
 * decoration like "v1.2". Returns a - b, so a plain ascending sort puts the
 * highest version last. */
export const compareVersions = (a: string, b: string): number => {
  const parse = (value: string) =>
    value.split(".").map((part) => parseInt(part.replace(/\D/g, ""), 10) || 0);
  const left = parse(a);
  const right = parse(b);
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const diff = (left[index] ?? 0) - (right[index] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
};

export interface WorkflowGroup {
  key: string;
  name: string;
  /** The live version's own name, for spotting renames between saves. */
  workflowName: string;
  /** Newest version first. */
  versions: WorkflowMinimal[];
  activeVersionId: string | null;
}

/** Group versions by the agent they belong to, newest version first.
 *
 * Versions of one workflow are separate rows sharing an ``agent_id`` and their
 * names can differ (a rename between saves), so grouping by name would split
 * them apart. The group is named after its agent, matching Agent Studio; a
 * workflow with no agent name falls back to its own.
 */
export const groupWorkflowVersions = (
  workflows: WorkflowMinimal[],
): WorkflowGroup[] => {
  const byWorkflow = new Map<string, WorkflowMinimal[]>();
  for (const workflow of workflows) {
    if (!workflow.id) continue;
    // Legacy rows without an agent stand alone; fall back to name so they still group.
    const key = workflow.agent_id ?? `name:${workflow.name}`;
    byWorkflow.set(key, [...(byWorkflow.get(key) ?? []), workflow]);
  }

  return Array.from(byWorkflow.entries())
    .map(([key, versions]): WorkflowGroup => {
      const ordered = [...versions].sort((a, b) =>
        compareVersions(b.version, a.version),
      );
      const active = ordered.find((workflow) => workflow.is_active_version);
      const named = active ?? ordered[0];
      return {
        key,
        name: named.agent_name || named.name,
        workflowName: named.name,
        versions: ordered,
        activeVersionId: active?.id ?? null,
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
};
