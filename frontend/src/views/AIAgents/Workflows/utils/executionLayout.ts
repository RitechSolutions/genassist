/**
 * A tiny, dependency-free layered ("Sugiyama-lite") DAG layout for the Execution view.
 *
 * The workflow editor stores hand-placed, often sparse coordinates — great for editing, poor for
 * reading a run at a glance (reactflow's fitView then zooms so far out that nodes become specks).
 * This recomputes compact left-to-right positions from the graph structure so the DAG is legible
 * regardless of the editor layout. Pure + defensive: unknown edges are ignored and cycles degrade
 * gracefully (unresolved nodes land in the first column) instead of throwing.
 */

export interface XY {
  x: number;
  y: number;
}

interface LayoutOptions {
  nodeW?: number;
  nodeH?: number;
  xGap?: number;
  yGap?: number;
}

export const computeLayeredLayout = (
  ids: string[],
  edges: { source: string; target: string }[],
  opts?: LayoutOptions
): Record<string, XY> => {
  const nodeW = opts?.nodeW ?? 210;
  const nodeH = opts?.nodeH ?? 68;
  const xGap = opts?.xGap ?? 110;
  const yGap = opts?.yGap ?? 30;

  const idSet = new Set(ids);
  const adj = new Map<string, string[]>();
  const indeg = new Map<string, number>();
  for (const id of ids) {
    adj.set(id, []);
    indeg.set(id, 0);
  }
  for (const e of edges) {
    if (!idSet.has(e.source) || !idSet.has(e.target) || e.source === e.target) continue;
    adj.get(e.source)!.push(e.target);
    indeg.set(e.target, (indeg.get(e.target) ?? 0) + 1);
  }

  // Longest-path layering via Kahn's algorithm.
  const layer = new Map<string, number>(ids.map((id) => [id, 0]));
  const remaining = new Map(indeg);
  const queue: string[] = ids.filter((id) => (indeg.get(id) ?? 0) === 0);
  while (queue.length) {
    const u = queue.shift()!;
    for (const v of adj.get(u) ?? []) {
      layer.set(v, Math.max(layer.get(v) ?? 0, (layer.get(u) ?? 0) + 1));
      remaining.set(v, (remaining.get(v) ?? 0) - 1);
      if ((remaining.get(v) ?? 0) === 0) queue.push(v);
    }
  }

  // Group by layer, preserving input order within a column.
  const byLayer = new Map<number, string[]>();
  for (const id of ids) {
    const l = layer.get(id) ?? 0;
    if (!byLayer.has(l)) byLayer.set(l, []);
    byLayer.get(l)!.push(id);
  }

  // Vertically centre each column around a shared axis so the graph reads tidily.
  const tallest = Math.max(1, ...Array.from(byLayer.values(), (g) => g.length));
  const columnPitch = nodeW + xGap;
  const rowPitch = nodeH + yGap;

  const positions: Record<string, XY> = {};
  for (const [l, group] of byLayer) {
    const offset = ((tallest - group.length) * rowPitch) / 2;
    group.forEach((id, i) => {
      positions[id] = { x: l * columnPitch, y: offset + i * rowPitch };
    });
  }
  return positions;
};
