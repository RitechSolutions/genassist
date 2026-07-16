/**
 * Auto-arrange: reproduces the hand-arrangement method used for these workflows as a pure,
 * dependency-free layout. Unlike the compact `executionLayout.ts` (read-only run view), this is
 * the layout applied when the user clicks "Arrange" in the editor.
 *
 * Left-to-right dataflow, built in two stages:
 *
 * 1. Tidy-tree base (`measure` + `place`):
 *    - Nodes sit on horizontal "lines" separated by an equal horizontal gap (H_GAP).
 *    - At a split (ANY node with >= 2 main outputs, e.g. a Conditional Router) the line divides into
 *      sibling branches, equally spaced vertically (BRANCH_GAP) and straddling the parent line
 *      symmetrically. Recursive: each subtree reserves vertical room by its own extent, so deeper
 *      subtrees widen the gaps of the splits above them.
 *    - Branches reconverge at a merge (ANY node where >= 2 branches meet, e.g. a Result Merger) onto
 *      the SAME line as the split that created them. Splits/merges are detected structurally, not by
 *      node type.
 *    - An AI agent sits on its line; its tools hang BELOW as vertical chains
 *      (agent -> toolBuilder -> ...nodes), top-aligned and growing down independently. The agent
 *      reserves horizontal room (tool columns never sit under a neighbour) and a vertical band sized
 *      to its deepest chain (branches below stay clear).
 *
 * 2. X re-flow for readability (after the tidy-tree pass, keeping each node's Y):
 *    - Clean single fan-out (splits directly cascaded, then branches, optional merge): branchers are
 *      racked on the left, the branch bodies are centred on one shared vertical axis (stacked on top
 *      of each other) between the right-most brancher and the left-most merger, and the mergers are
 *      racked on the right.
 *    - Otherwise (sequential/nested splits, or merges interleaved with splits): the tidy-tree layout
 *      is kept as-is.
 *    - In both cases, edges that would render as near-straight bezier lines (endpoints far apart on
 *      one axis but close on the other) are given extra room on the short axis so they keep a curve.
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
  /** Vertical drop from the agent's bottom to the tool tops (widened for wide clusters so the outer
   *  columns' connections curve instead of running near-horizontal). */
  startGap: number;
}

export const computeAutoArrangeLayout = (input: AutoArrangeInput): Record<string, XY> => {
  const NODE_W = 400; // node-width fallback when a node hasn't been measured yet
  const H_GAP = 120; // every horizontal gap: between nodes on a line AND between an agent's tool columns
  const V_GAP = 80; // base vertical gap: within a tool chain, the tool-band reservation, etc.
  const EST_H = 200; // node-height fallback when a node hasn't been measured yet
  const COMPONENT_GAP = V_GAP * 3;
  // Vertical gap between sibling branches — larger than the base V_GAP so branches are easy to tell
  // apart in dense workflows. (Only sibling-branch spacing uses this; tool chains still use V_GAP.)
  const BRANCH_GAP = V_GAP * 2.5;
  // Bezier edges collapse to a near-straight line when their endpoints are far apart on one axis but
  // close on the other. CURVE_RATIO is the minimum primary-axis gap we keep relative to the cross-
  // axis distance so the curve keeps a visible bend. Higher = more pronounced curves (wider/taller
  // layout); used by the fan-out/fan-in curving, the router-cascade spread, and the curve-only fallback.
  const CURVE_RATIO = 0.4;
  // Tools drop below an agent by this coefficient × √(outer-column offset) — sub-linear, so a very
  // wide cluster doesn't fall absurdly far. Narrow clusters stay at ~V_GAP (Version 1 spacing).
  const TOOL_DROP_COEFF = 6;

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

  // ── Classify edges into main-flow vs tool-attachment ─────────────────────────────────────────
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

  // ── Mark tool subgraphs ──────────────────────────────────────────────────────────────────────
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

  // ── Tool cluster sizing per agent (precompute) ───────────────────────────────────────────────
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
    // Widen the drop to the tools in proportion to how far the outer-most column sits from the agent
    // centre, so those outer columns' connections curve rather than run near-horizontal. A single /
    // narrow cluster has offset ~0, so startGap stays at V_GAP (i.e. Version 1 spacing).
    let maxColOffset = 0;
    let scan = -clusterWidth / 2;
    for (const c of columns) {
      maxColOffset = Math.max(maxColOffset, Math.abs(scan + c.width / 2));
      scan += c.width + H_GAP;
    }
    const startGap = Math.max(V_GAP, TOOL_DROP_COEFF * Math.sqrt(maxColOffset));
    const bandHeight = columns.length
      ? startGap + Math.max(...columns.map((c) => c.height))
      : 0;
    clusters.set(agentId, { columns, clusterWidth, bandHeight, startGap });
  }

  const clusterWidthOf = (id: string) => clusters.get(id)?.clusterWidth ?? 0;
  const toolBandOf = (id: string) => clusters.get(id)?.bandHeight ?? 0;

  const pos: Record<string, XY> = {};

  // ── merge detection: the node that closes a split ────────────────────────────────────────────
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
  // A merge is where branches reconverge: the nearest common main-descendant of ALL the split's
  // children that has >= 2 incoming main edges. ANY node type can merge branches — the Result
  // Merger (aggregatorNode) is just the common example — so detection is structural, not by type.
  const commonMerge = (split: string, succ: string[]): string | null => {
    const sets = succ.map((c) => descendantsInclusive(c));
    let inter = sets[0];
    for (let i = 1; i < sets.length; i++) inter = new Set([...inter].filter((x) => sets[i].has(x)));
    const candidates = [...inter].filter((id) => id !== split && (mainIn.get(id) ?? 0) >= 2);
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
        // s is the smallest equal gap that leaves BRANCH_GAP of clearance between adjacent subtrees.
        const n = exts.length;
        let s = 0;
        for (let i = 0; i < n - 1; i++) s = Math.max(s, exts[i].down + exts[i + 1].up + BRANCH_GAP);
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
    const topY = pos[agentId].y + height(agentId) + cluster.startGap;
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
        for (let i = 0; i < n - 1; i++) s = Math.max(s, exts[i].down + exts[i + 1].up + BRANCH_GAP);
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

  // ── X re-flow pass ───────────────────────────────────────────────────────────────────────────
  // Branchers = main out-degree >= 2; mergers = main in-degree >= 2. When the graph is a clean single
  // fan-out (see the guard below) we keep each node's tidy-tree Y and only re-flow X: branchers stay
  // racked on the left, the branch bodies are centred on one shared vertical axis (stacked on top of
  // each other) between the right-most brancher and the left-most merger, and the merger zone +
  // trailing trunk slide in just past the content. Any other shape takes the curve-only fallback.
  const branchers = [...idSet].filter(
    (id) => !toolNodes.has(id) && orderedSucc(id).length >= 2 && pos[id],
  );
  const mergers = [...idSet].filter(
    (id) => !toolNodes.has(id) && (mainIn.get(id) ?? 0) >= 2 && pos[id],
  );
  const rightmostBrancherX = branchers.length
    ? Math.max(...branchers.map((id) => pos[id].x + width(id)))
    : -Infinity;
  const leftmostMergerX = mergers.length
    ? Math.min(...mergers.map((id) => pos[id].x))
    : Infinity;

  // Reverse main adjacency (used by the centering pass and the fallback curve pass below).
  const revAdj = new Map<string, string[]>();
  for (const [u, list] of mainAdj) {
    for (const e of list) {
      const arr = revAdj.get(e.target);
      if (arr) arr.push(u);
      else revAdj.set(e.target, [u]);
    }
  }

  const brancherSet = new Set(branchers);
  const mergerSet = new Set(mergers);
  // forward = reachable from a brancher; canReachBrancher = upstream of a brancher. A node in BOTH
  // sits *between* two branchers.
  const forward = reachFrom(branchers.flatMap((b) => orderedSucc(b)));
  const canReachBrancher = new Set<string>();
  {
    const bstack = branchers.flatMap((b) => revAdj.get(b) ?? []);
    while (bstack.length) {
      const u = bstack.pop()!;
      if (canReachBrancher.has(u)) continue;
      canReachBrancher.add(u);
      for (const p of revAdj.get(u) ?? []) if (!canReachBrancher.has(p)) bstack.push(p);
    }
  }
  // Real content strung *between* two splits. If any exists, the splits are sequential / nested (a
  // split sitting after content) rather than one clean fan-out — centering can't place those (it
  // would drag a later split's branches back to the left of the split), so they take the curve-only
  // fallback instead.
  const betweenBranchers = [...idSet].filter(
    (id) =>
      !!pos[id] &&
      !toolNodes.has(id) &&
      !brancherSet.has(id) &&
      !mergerSet.has(id) &&
      forward.has(id) &&
      canReachBrancher.has(id),
  );

  // Clean single fan-out: every brancher sits left of every merger (leftmostMergerX is +Infinity with
  // no merges, so branch-only graphs qualify) AND nothing but gates sits between the branchers.
  if (
    branchers.length &&
    rightmostBrancherX + H_GAP < leftmostMergerX &&
    betweenBranchers.length === 0
  ) {
    const backward = new Set<string>(); // can reach a merger
    const rstack = mergers.flatMap((m) => revAdj.get(m) ?? []);
    while (rstack.length) {
      const u = rstack.pop()!;
      if (backward.has(u)) continue;
      backward.add(u);
      for (const v of revAdj.get(u) ?? []) if (!backward.has(v)) rstack.push(v);
    }
    // Content = the branch bodies: reachable from a brancher, not a gate or tool, and left of the
    // merger zone. When there ARE merges we also require the node to reach a merger (so the post-merge
    // trunk is excluded); with no merges, every branch body counts.
    const contentSet = new Set(
      [...idSet].filter(
        (id) =>
          !!pos[id] &&
          !toolNodes.has(id) &&
          !brancherSet.has(id) &&
          !mergerSet.has(id) &&
          forward.has(id) &&
          (!mergers.length || backward.has(id)) &&
          pos[id].x < leftmostMergerX,
      ),
    );

    // Spread the router cascade: a brancher feeding another brancher that jumps far in Y but little in
    // X collapses to a near-straight edge. Push each brancher right in proportion to that Y gap so the
    // edge curves; process left-to-right so shifts propagate down the cascade. Anchors are the fixed
    // nodes to the left (other branchers + the pre-branch trunk).
    const scaffoldOrder = [...branchers].sort((a, b) => pos[a].x - pos[b].x);
    for (const v of scaffoldOrder) {
      let need = pos[v].x;
      for (const u of revAdj.get(v) ?? []) {
        if (contentSet.has(u) || mergerSet.has(u) || toolNodes.has(u)) continue;
        const dy = Math.abs(pos[u].y + height(u) / 2 - (pos[v].y + height(v) / 2));
        need = Math.max(need, pos[u].x + width(u) + Math.max(H_GAP, CURVE_RATIO * dy));
      }
      pos[v].x = need;
    }

    if (contentSet.size) {
      const toolsOfNode = (id: string): string[] =>
        (clusters.get(id)?.columns ?? []).flatMap((c) => c.ids);

      // Group content into connected chains (components via main edges, treated as undirected).
      const seen = new Set<string>();
      const chains: string[][] = [];
      for (const id of contentSet) {
        if (seen.has(id)) continue;
        const comp: string[] = [];
        const stack = [id];
        while (stack.length) {
          const u = stack.pop()!;
          if (seen.has(u)) continue;
          seen.add(u);
          comp.push(u);
          for (const v of orderedSucc(u)) if (contentSet.has(v) && !seen.has(v)) stack.push(v);
          for (const v of revAdj.get(u) ?? []) if (contentSet.has(v) && !seen.has(v)) stack.push(v);
        }
        chains.push(comp);
      }

      // A chain's horizontal footprint includes any tool clusters hanging off its agents.
      const spanOf = (chain: string[]) => {
        let lo = Infinity;
        let hi = -Infinity;
        for (const id of [...chain, ...chain.flatMap(toolsOfNode)]) {
          if (!pos[id]) continue;
          lo = Math.min(lo, pos[id].x);
          hi = Math.max(hi, pos[id].x + width(id));
        }
        return { lo, hi };
      };

      // Recompute after the cascade spread above, so content clears the widened brancher zone.
      const corridorLeft = Math.max(...branchers.map((id) => pos[id].x + width(id))) + H_GAP;
      const maxW = Math.max(
        ...chains.map((c) => {
          const s = spanOf(c);
          return s.hi - s.lo;
        }),
      );
      const axis = corridorLeft + maxW / 2;

      // Centre every chain (and its tools) on the axis — branches stack on top of one another.
      const contentAndTools = new Set<string>(contentSet);
      for (const chain of chains) {
        const { lo, hi } = spanOf(chain);
        const shift = axis - (lo + hi) / 2;
        for (const id of [...chain, ...chain.flatMap(toolsOfNode)]) {
          if (pos[id]) pos[id].x += shift;
          contentAndTools.add(id);
        }
      }

      // Curve the fan-OUT: a brancher connecting to content that's far in Y but close in X makes a
      // near-straight edge. Slide ALL content right by the largest deficit so even the most
      // vertically-distant branch keeps enough horizontal room to curve.
      let fanOutShift = 0;
      for (const b of branchers) {
        const bRight = pos[b].x + width(b);
        const bMidY = pos[b].y + height(b) / 2;
        for (const t of orderedSucc(b)) {
          if (!contentSet.has(t)) continue;
          const dx = pos[t].x - bRight;
          const dy = Math.abs(pos[t].y + height(t) / 2 - bMidY);
          fanOutShift = Math.max(fanOutShift, CURVE_RATIO * dy - dx);
        }
      }
      if (fanOutShift > 0.001) {
        for (const id of contentAndTools) if (pos[id]) pos[id].x += fanOutShift;
      }

      // Place the merger zone just past the content — but far enough right that the fan-IN edges
      // (content -> merger) also keep a curve (mirror of the fan-out).
      let mergerX = -Infinity;
      for (const id of contentAndTools) if (pos[id]) mergerX = Math.max(mergerX, pos[id].x + width(id));
      mergerX += H_GAP;
      for (const m of mergers) {
        const mMidY = pos[m].y + height(m) / 2;
        for (const s of revAdj.get(m) ?? []) {
          if (!contentSet.has(s)) continue;
          const dy = Math.abs(pos[s].y + height(s) / 2 - mMidY);
          mergerX = Math.max(mergerX, pos[s].x + width(s) + CURVE_RATIO * dy);
        }
      }
      // Slide the merger zone + trailing trunk so the left-most merger lands at mergerX (a no-op when
      // there are no merges — leftmostMergerX is +Infinity, so nothing falls in the right region).
      const delta = mergers.length ? mergerX - leftmostMergerX : 0;
      const rightRegion: string[] = [];
      for (const id of idSet) {
        if (pos[id] && !contentAndTools.has(id) && pos[id].x >= leftmostMergerX - 0.001) {
          if (Math.abs(delta) > 0.001) pos[id].x += delta;
          rightRegion.push(id);
        }
      }
      // Spread the merger zone the same way as the fan-out: any edge feeding a merger (from a branch
      // body, a node between two mergers, or another merger) that jumps far in Y but little in X gets
      // extra room. Left-to-right; horizontal trailing-trunk edges (~0 Y jump) just keep H_GAP & follow.
      rightRegion.sort((a, b) => pos[a].x - pos[b].x);
      for (const v of rightRegion) {
        let need = pos[v].x;
        for (const u of revAdj.get(v) ?? []) {
          if (toolNodes.has(u)) continue;
          const dy = Math.abs(pos[u].y + height(u) / 2 - (pos[v].y + height(v) / 2));
          need = Math.max(need, pos[u].x + width(u) + Math.max(H_GAP, CURVE_RATIO * dy));
        }
        pos[v].x = need;
      }
    }
  } else if (branchers.length) {
    // Not a clean single fan-out — either merges interleave with the splits (a merger left of a later
    // brancher) or the splits are sequential/nested (real content between two splits). No corridor to
    // centre in, so keep the tidy-tree layout and just curve the edges: where
    // an incoming main edge is too straight (ΔX < CURVE_RATIO·ΔY), push the target RIGHT together with
    // its ENTIRE downstream branch, so the branch just translates and its internal spacing is
    // preserved — the shifted node never crowds the next node. Process left-to-right so nested
    // branches accumulate their parents' shifts. An agent's tool cluster rides along too.
    const toolsOfId = (id: string) => (clusters.get(id)?.columns ?? []).flatMap((c) => c.ids);
    const translateSubtree = (root: string, dx: number) => {
      const seen = new Set<string>();
      const stack = [root];
      while (stack.length) {
        const u = stack.pop()!;
        if (seen.has(u)) continue;
        seen.add(u);
        if (pos[u]) pos[u].x += dx;
        for (const t of toolsOfId(u)) if (pos[t]) pos[t].x += dx;
        for (const w of orderedSucc(u)) if (!seen.has(w)) stack.push(w);
      }
    };
    const order = [...idSet].filter((id) => !toolNodes.has(id) && pos[id]);
    order.sort((a, b) => pos[a].x - pos[b].x);
    for (const v of order) {
      let deficit = 0;
      for (const u of revAdj.get(v) ?? []) {
        if (toolNodes.has(u) || !pos[u]) continue;
        const dy = Math.abs(pos[u].y + height(u) / 2 - (pos[v].y + height(v) / 2));
        deficit = Math.max(
          deficit,
          pos[u].x + width(u) + Math.max(H_GAP, CURVE_RATIO * dy) - pos[v].x,
        );
      }
      if (deficit > 0.001) translateSubtree(v, deficit);
    }
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
