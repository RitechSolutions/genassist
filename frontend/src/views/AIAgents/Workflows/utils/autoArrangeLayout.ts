/**
 * Auto-arrange: reproduces the hand-arrangement method used for these workflows as a pure,
 * dependency-free layout. Unlike the compact `executionLayout.ts` (read-only run view), this is
 * the layout applied when the user clicks "Rearrange" in the editor.
 *
 * The method (left-to-right dataflow):
 *  - Nodes sit on horizontal "lines"; nodes on a line are centred on a shared vertical axis and
 *    separated by an equal horizontal gap (H_GAP).
 *  - At a split (a node with >= 2 main outputs, e.g. a Conditional Router) the line divides into
 *    sibling branches, equally spaced vertically (V_GAP) and straddling the parent line
 *    symmetrically. This is recursive (tidy-tree): each subtree reserves vertical room by its own
 *    extent, so deeper subtrees widen the gaps of the splits above them. Siblings are also
 *    centre-aligned horizontally (a short branch sits under the middle of a longer sibling).
 *  - Branches feeding the same Result Merger (aggregatorNode) reconverge onto the SAME line as the
 *    split that created them (split/merge is symmetric).
 *  - An AI agent sits on its line; its tools hang BELOW as vertical chains
 *    (agent -> toolBuilder -> ...nodes). All of an agent's chains are top-aligned (same start Y)
 *    and grow down independently, so unequal chains end at different depths. Chains are spaced by
 *    H_GAP and centred on the agent. An agent reserves horizontal room (so tool columns never sit
 *    under a neighbour) and a vertical band sized to its deepest chain (so branches below stay
 *    clear).
 *
 * Pure + defensive, mirroring executionLayout.ts: cycles/back-edges degrade gracefully (dropped
 * via a visited guard), unknown edges are ignored, and unreachable/orphan nodes land in a trailing
 * row instead of throwing.
 */

import { NodeHandler } from "../types/nodes";
import { XY } from "./executionLayout";

export interface AutoArrangeNode {
  id: string;
  type?: string;
  width?: number | null;
  height?: number | null;
  data?: { handlers?: NodeHandler[] };
}

export interface AutoArrangeEdge {
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface AutoArrangeInput {
  nodes: AutoArrangeNode[];
  edges: AutoArrangeEdge[];
}

export interface AutoArrangeOptions {
  /** Node width fallback when a node has not been measured yet. */
  nodeW?: number;
  /** Every horizontal gap: between nodes on a line AND between an agent's tool columns. */
  hGap?: number;
  /** Every vertical gap: between sibling branches AND between nodes within a tool chain. */
  vGap?: number;
  /** Node height fallback when a node has not been measured yet. */
  estHeight?: number;
}

interface Extent {
  up: number;
  down: number;
}

interface ToolColumn {
  ids: string[];
  width: number;
  height: number;
}

interface ToolCluster {
  columns: ToolColumn[];
  clusterWidth: number;
  bandHeight: number;
}

export const computeAutoArrangeLayout = (
  input: AutoArrangeInput,
  opts?: AutoArrangeOptions,
): Record<string, XY> => {
  const NODE_W = opts?.nodeW ?? 400;
  const H_GAP = opts?.hGap ?? 120;
  const V_GAP = opts?.vGap ?? 80;
  const EST_H = opts?.estHeight ?? 200;
  const COMPONENT_GAP = V_GAP * 3;

  const { nodes, edges } = input;
  const idSet = new Set(nodes.map((n) => n.id));
  const nodeById = new Map(nodes.map((n) => [n.id, n]));

  const width = (id: string) => nodeById.get(id)?.width || NODE_W;
  const height = (id: string) => nodeById.get(id)?.height || EST_H;
  const typeOf = (id: string) => nodeById.get(id)?.type;

  // Resolve a handle id to its side ("left"/"right"/"top"/"bottom").
  const handlerPos = (id: string, handle?: string | null): string | undefined => {
    if (!handle) return undefined;
    return nodeById.get(id)?.data?.handlers?.find((h) => h.id === handle)?.position;
  };
  const handlerIndex = (id: string, handle?: string | null): number => {
    const handlers = nodeById.get(id)?.data?.handlers;
    if (!handlers || !handle) return Number.MAX_SAFE_INTEGER;
    const i = handlers.findIndex((h) => h.id === handle);
    return i === -1 ? Number.MAX_SAFE_INTEGER : i;
  };

  // ── Phase 0: classify edges into main-flow vs tool-attachment ────────────────────────────────
  // Main-flow edge: source handle on "right", target handle on "left" (or, defensively, neither
  // endpoint on the tool axis). Tool-attachment edge: source on "top" (a *_tool output) or target
  // on "bottom" (an agent's input_tools) — the target is the agent, the source is the tool root.
  const mainAdj = new Map<string, { target: string; order: number }[]>();
  const mainIn = new Map<string, number>();
  const toolsOf = new Map<string, string[]>(); // agentId -> tool root ids
  for (const id of idSet) {
    mainAdj.set(id, []);
    mainIn.set(id, 0);
  }

  for (const e of edges) {
    if (!idSet.has(e.source) || !idSet.has(e.target) || e.source === e.target) continue;
    const sPos = handlerPos(e.source, e.sourceHandle);
    const tPos = handlerPos(e.target, e.targetHandle);
    const isTool = sPos === "top" || tPos === "bottom";
    if (isTool) {
      const roots = toolsOf.get(e.target) ?? [];
      if (!roots.includes(e.source)) roots.push(e.source);
      toolsOf.set(e.target, roots);
    } else {
      mainAdj.get(e.source)!.push({ target: e.target, order: handlerIndex(e.source, e.sourceHandle) });
      mainIn.set(e.target, (mainIn.get(e.target) ?? 0) + 1);
    }
  }

  // Order each node's outgoing main edges by source-handle index (router true above false), then id.
  for (const list of mainAdj.values()) {
    list.sort((a, b) => a.order - b.order || (a.target < b.target ? -1 : 1));
  }
  const orderedSucc = (id: string): string[] => (mainAdj.get(id) ?? []).map((e) => e.target);

  // ── Phase 2: mark tool subgraphs ─────────────────────────────────────────────────────────────
  const toolRoots = new Set<string>();
  for (const roots of toolsOf.values()) roots.forEach((r) => toolRoots.add(r));

  // Real main starts drive the main flow. A tool root looks like a start (main-indegree 0) so it
  // is explicitly excluded here.
  const mainStarts = nodes
    .map((n) => n.id)
    .filter((id) => !toolRoots.has(id) && (typeOf(id) === "chatInputNode" || (mainIn.get(id) ?? 0) === 0));

  const reachFrom = (seeds: Iterable<string>): Set<string> => {
    const seen = new Set<string>();
    const stack = [...seeds];
    while (stack.length) {
      const u = stack.pop()!;
      if (seen.has(u)) continue;
      seen.add(u);
      for (const v of orderedSucc(u)) if (!seen.has(v)) stack.push(v);
    }
    return seen;
  };

  const reachableFromMain = reachFrom(mainStarts);
  const reachableFromTools = reachFrom(toolRoots);
  // A node reachable from a tool root but NOT from a main start belongs to a tool chain.
  const toolNodes = new Set<string>();
  for (const id of reachableFromTools) if (!reachableFromMain.has(id)) toolNodes.add(id);

  // ── Phase 5 (precompute): tool cluster sizing per agent ──────────────────────────────────────
  const collectColumn = (root: string): string[] => {
    const ids: string[] = [];
    const seen = new Set<string>();
    const stack = [root];
    while (stack.length) {
      const u = stack.pop()!;
      if (seen.has(u) || !toolNodes.has(u)) continue;
      seen.add(u);
      ids.push(u);
      for (const v of orderedSucc(u)) if (!seen.has(v)) stack.push(v);
    }
    return ids;
  };

  const clusters = new Map<string, ToolCluster>();
  for (const [agentId, roots] of toolsOf) {
    const columns: ToolColumn[] = roots.map((root) => {
      const ids = collectColumn(root);
      const w = ids.length ? Math.max(...ids.map(width)) : NODE_W;
      const h = ids.reduce((s, id) => s + height(id), 0) + Math.max(0, ids.length - 1) * V_GAP;
      return { ids, width: w, height: h };
    });
    const clusterWidth =
      columns.reduce((s, c) => s + c.width, 0) + Math.max(0, columns.length - 1) * H_GAP;
    const bandHeight = columns.length ? V_GAP + Math.max(...columns.map((c) => c.height)) : 0;
    clusters.set(agentId, { columns, clusterWidth, bandHeight });
  }

  const clusterWidthOf = (id: string) => clusters.get(id)?.clusterWidth ?? 0;
  const toolBandOf = (id: string) => clusters.get(id)?.bandHeight ?? 0;

  const pos: Record<string, XY> = {};

  // ── merge detection: the aggregator that closes a split ──────────────────────────────────────
  const descendantsInclusive = (start: string): Set<string> => {
    const seen = new Set<string>();
    const stack = [start];
    while (stack.length) {
      const u = stack.pop()!;
      if (seen.has(u)) continue;
      seen.add(u);
      for (const v of orderedSucc(u)) if (!seen.has(v)) stack.push(v);
    }
    return seen;
  };
  const distanceFrom = (start: string, target: string): number => {
    const dist = new Map<string, number>([[start, 0]]);
    const queue = [start];
    while (queue.length) {
      const u = queue.shift()!;
      if (u === target) return dist.get(u)!;
      for (const v of orderedSucc(u))
        if (!dist.has(v)) {
          dist.set(v, dist.get(u)! + 1);
          queue.push(v);
        }
    }
    return Number.MAX_SAFE_INTEGER;
  };
  const commonMerge = (split: string, succ: string[]): string | null => {
    const sets = succ.map((c) => descendantsInclusive(c));
    let inter = sets[0];
    for (let i = 1; i < sets.length; i++) inter = new Set([...inter].filter((x) => sets[i].has(x)));
    const candidates = [...inter].filter((id) => typeOf(id) === "aggregatorNode");
    if (!candidates.length) return null;
    return candidates.reduce((best, id) =>
      distanceFrom(split, id) < distanceFrom(split, best) ? id : best,
    );
  };

  // ── measure: vertical extent (above/below the line's centre) of a sub-flow ───────────────────
  const measure = (entry: string, stop: Set<string>, guard: Set<string>): Extent => {
    let up = 0;
    let down = 0;
    let cur: string | null = entry;
    while (cur && !stop.has(cur) && !guard.has(cur)) {
      guard.add(cur);
      const h = height(cur);
      up = Math.max(up, h / 2);
      down = Math.max(down, h / 2 + toolBandOf(cur));
      const succ = orderedSucc(cur);
      if (succ.length >= 2) {
        const M = commonMerge(cur, succ);
        const childStop = M ? new Set([...stop, M]) : stop;
        const exts = succ.map((c) => measure(c, childStop, guard));
        // Children are EQUALLY spaced and symmetric about this line: line_i = centerY + (i-mid)*s.
        // s is the smallest equal gap that avoids any sibling subtree overlapping its neighbour.
        const n = exts.length;
        let s = 0;
        for (let i = 0; i < n - 1; i++) s = Math.max(s, exts[i].down + exts[i + 1].up + V_GAP);
        const half = ((n - 1) / 2) * s;
        up = Math.max(up, half + exts[0].up);
        down = Math.max(down, half + exts[n - 1].down);
        // Only the top-most split that introduces a merge OWNS it. If M is already a stopper from
        // an ancestor, that ancestor will place it and continue the line past it — not us.
        const ownM = M && !stop.has(M) ? M : null;
        if (ownM) {
          guard.add(ownM);
          up = Math.max(up, height(ownM) / 2);
          down = Math.max(down, height(ownM) / 2 + toolBandOf(ownM));
          cur = orderedSucc(ownM)[0] ?? null;
        } else {
          cur = null;
        }
      } else {
        cur = succ[0] ?? null;
      }
    }
    return { up, down };
  };

  // ── place: assign positions; returns rightmost x edge and the ids it placed (for shifting) ────
  const placeGuard = new Set<string>();

  const placeToolChains = (agentId: string): string[] => {
    const cluster = clusters.get(agentId);
    if (!cluster || !cluster.columns.length) return [];
    const placed: string[] = [];
    const centerX = pos[agentId].x + width(agentId) / 2;
    const topY = pos[agentId].y + height(agentId) + V_GAP;
    let offset = centerX - cluster.clusterWidth / 2;
    for (const col of cluster.columns) {
      const colCenterX = offset + col.width / 2;
      let y = topY;
      for (const id of col.ids) {
        pos[id] = { x: colCenterX - width(id) / 2, y };
        placed.push(id);
        y += height(id) + V_GAP;
      }
      offset += col.width + H_GAP;
    }
    return placed;
  };

  // Returns maxX – rightmost edge of the WHOLE subtree – plus the ids it placed (for shifting).
  const place = (
    entry: string,
    centerY: number,
    startX: number,
    stop: Set<string>,
  ): { maxX: number; placed: string[] } => {
    const placed: string[] = [];
    let cur: string | null = entry;
    let x = startX;
    let maxX = startX;
    while (cur && !stop.has(cur) && !placeGuard.has(cur)) {
      placeGuard.add(cur);
      const w = width(cur);
      const footprint = Math.max(w, clusterWidthOf(cur));
      const nodeX = x + (footprint - w) / 2;
      pos[cur] = { x: nodeX, y: centerY - height(cur) / 2 };
      placed.push(cur);
      if (clusterWidthOf(cur) > 0) placed.push(...placeToolChains(cur));
      // Use the full reserved footprint (node OR its wider tool cluster) so a downstream merger
      // clears an agent's tool columns instead of landing on top of them.
      maxX = Math.max(maxX, x + footprint);

      const succ = orderedSucc(cur);
      if (succ.length >= 2) {
        const M = commonMerge(cur, succ);
        const childStop = M ? new Set([...stop, M]) : stop;
        const measGuard = new Set<string>();
        const exts = succ.map((c) => measure(c, childStop, measGuard));
        const childStartX = x + footprint + H_GAP;

        // Equal spacing, symmetric about this line (see measure): the split's line is exactly the
        // midpoint of its children's lines (middle child on the line; even count → gap midpoint).
        const n = exts.length;
        let s = 0;
        for (let i = 0; i < n - 1; i++) s = Math.max(s, exts[i].down + exts[i + 1].up + V_GAP);
        const mid = (n - 1) / 2;
        const infos = succ.map((c, i) =>
          place(c, centerY + (i - mid) * s, childStartX, childStop),
        );

        // Centre-align siblings horizontally: shift shorter branches right so every branch's centre
        // lines up under the longest sibling's centre (a short branch sits under the middle of a
        // longer one, and merging branches line up in a column before their merger).
        const centerOf = (r: (typeof infos)[number]) => (childStartX + r.maxX) / 2;
        const maxCenter = Math.max(...infos.map(centerOf));
        infos.forEach((r) => {
          const shift = maxCenter - centerOf(r);
          if (shift > 0.001) {
            r.placed.forEach((id) => {
              pos[id].x += shift;
            });
            r.maxX += shift;
          }
          placed.push(...r.placed);
          maxX = Math.max(maxX, r.maxX);
        });

        // Only the top-most split that introduces a merge OWNS it (see measure()). A descendant
        // whose computed merge is already a stopper must NOT re-place it, or the merger would be
        // overwritten at multiple lines and get separated from its own trailing chain.
        const ownM = M && !stop.has(M) ? M : null;
        if (ownM) {
          const regionRight = Math.max(...infos.map((r) => r.maxX));
          const mX = regionRight + H_GAP;
          placeGuard.add(ownM);
          pos[ownM] = { x: mX, y: centerY - height(ownM) / 2 };
          placed.push(ownM);
          if (clusterWidthOf(ownM) > 0) placed.push(...placeToolChains(ownM));
          maxX = Math.max(maxX, mX + width(ownM));
          x = mX + width(ownM) + H_GAP;
          cur = orderedSucc(ownM)[0] ?? null;
        } else {
          cur = null;
        }
      } else {
        x = x + footprint + H_GAP;
        cur = succ[0] ?? null;
      }
    }
    return { maxX, placed };
  };

  // ── Lay out each component; stack vertically ─────────────────────────────────────────────────
  let offsetY = 0;
  const layoutComponent = (start: string) => {
    if (placeGuard.has(start)) return;
    const ext = measure(start, new Set(), new Set());
    const centerY = offsetY + ext.up;
    place(start, centerY, 0, new Set());
    offsetY = centerY + ext.down + COMPONENT_GAP;
  };

  mainStarts.forEach(layoutComponent);
  // Cycle-only main components (no indegree-0 seed): pick any remaining main node as a pseudo-start.
  for (const n of nodes) {
    if (!toolNodes.has(n.id) && !placeGuard.has(n.id)) layoutComponent(n.id);
  }

  // ── Orphans / never-placed nodes → trailing row ──────────────────────────────────────────────
  let ox = 0;
  for (const n of nodes) {
    if (pos[n.id]) continue;
    pos[n.id] = { x: ox, y: offsetY };
    ox += width(n.id) + H_GAP;
  }

  // ── Normalise so the top-left of the graph is the origin ─────────────────────────────────────
  const values = Object.values(pos);
  if (values.length) {
    const minX = Math.min(...values.map((p) => p.x));
    const minY = Math.min(...values.map((p) => p.y));
    for (const id of Object.keys(pos)) {
      pos[id] = { x: pos[id].x - minX, y: pos[id].y - minY };
    }
  }

  return pos;
};
