import type { Edge, Node } from "reactflow";

/**
 * Node groups ("sections") — a purely visual, editor-only container that frames related nodes
 * under a user-defined name. A group is stored in the workflow's `nodes` list like any other
 * React Flow node, but it is never executed: the backend engine drops it on load
 * (`EDITOR_ONLY_NODE_TYPES` in workflow_engine.py) and it has no handles, so no edge can
 * ever touch it.
 *
 * Data model (all optional, so workflows without groups are unchanged):
 *   group node:  { type: "groupNode", position, style: { width, height }, zIndex, data: { name } }
 *   child node:  { parentId: "<group id>", position: <relative to the group's top-left> }
 *
 * Groups are one level deep (a group never has a parent). Everything here is pure so the
 * coordinate maths can be unit tested; GraphFlow wires these into React state.
 */

export const GROUP_NODE_TYPE = "groupNode";
export const DEFAULT_GROUP_NAME = "Untitled Group";

/** Space kept between a group's border and its outermost children. */
export const GROUP_PADDING = 40;
/** Extra room above the children for the group's title bar. */
export const GROUP_HEADER_HEIGHT = 56;
export const GROUP_MIN_WIDTH = 240;
export const GROUP_MIN_HEIGHT = 140;

/**
 * Groups render BEHIND everything, including edges. React Flow v11 draws edges in an SVG layer at
 * z-index 0 and adds 1000 to a selected node's z-index, so -1001 keeps a group under the edges
 * even while it is selected (-1). Children take max(parent z, own z) = 0, i.e. they are unaffected.
 */
export const GROUP_Z_INDEX = -1001;

// Fallbacks for nodes React Flow hasn't measured yet.
const DEFAULT_NODE_WIDTH = 300;
const DEFAULT_NODE_HEIGHT = 150;

export interface XY {
  x: number;
  y: number;
}

export interface Rect extends XY {
  width: number;
  height: number;
}

export interface GroupNodeData {
  name?: string;
  /** Palette key from nodeTypes/group/groupColors (absent = default neutral look). */
  color?: string;
}

export const isGroupNode = (node?: Pick<Node, "type"> | null): boolean =>
  node?.type === GROUP_NODE_TYPE;

/**
 * The parent group id. Persisted state uses `parentId`; the render layer maps it to v11's
 * `parentNode` (see toRenderableNodes), so nodes handed back by React Flow callbacks carry that.
 */
export const getParentId = (node: Node): string | undefined =>
  node.parentId || node.parentNode || undefined;

const withoutParent = (node: Node): Node => {
  const { parentId, parentNode, extent, expandParent, ...rest } = node;
  return rest as Node;
};

const withParent = (node: Node, parentId: string): Node => ({
  ...withoutParent(node),
  parentId,
});

const toNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = parseFloat(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
};

/**
 * Current size of a node. A group's size is owned by `style` (we write it there and React Flow's
 * resizer does too), so it wins over the measured width/height, which lag one frame behind.
 */
export const getNodeSize = (node: Node): { width: number; height: number } => {
  const styleWidth = toNumber(node.style?.width);
  const styleHeight = toNumber(node.style?.height);
  if (isGroupNode(node)) {
    return {
      width: styleWidth ?? toNumber(node.width) ?? GROUP_MIN_WIDTH,
      height: styleHeight ?? toNumber(node.height) ?? GROUP_MIN_HEIGHT,
    };
  }
  return {
    width: toNumber(node.width) ?? styleWidth ?? DEFAULT_NODE_WIDTH,
    height: toNumber(node.height) ?? styleHeight ?? DEFAULT_NODE_HEIGHT,
  };
};

const indexById = (nodes: Node[]) => new Map(nodes.map((n) => [n.id, n]));

/** Canvas (root-level) position of a node, walking up its parent chain. */
export const getAbsolutePosition = (node: Node, byId: Map<string, Node>): XY => {
  let x = node.position?.x ?? 0;
  let y = node.position?.y ?? 0;
  const seen = new Set([node.id]);
  let parentId = getParentId(node);
  while (parentId && !seen.has(parentId)) {
    const parent = byId.get(parentId);
    if (!parent) break;
    x += parent.position?.x ?? 0;
    y += parent.position?.y ?? 0;
    seen.add(parentId);
    parentId = getParentId(parent);
  }
  return { x, y };
};

export const getAbsoluteRect = (node: Node, byId: Map<string, Node>): Rect => ({
  ...getAbsolutePosition(node, byId),
  ...getNodeSize(node),
});

const boundsOf = (rects: Rect[]) => ({
  minX: Math.min(...rects.map((r) => r.x)),
  minY: Math.min(...rects.map((r) => r.y)),
  maxX: Math.max(...rects.map((r) => r.x + r.width)),
  maxY: Math.max(...rects.map((r) => r.y + r.height)),
});

/** The rect a group needs to frame `rects` (in the same coordinate space) with padding + title bar. */
const frameAround = (rects: Rect[]): Rect => {
  const { minX, minY, maxX, maxY } = boundsOf(rects);
  const x = minX - GROUP_PADDING;
  const y = minY - GROUP_PADDING - GROUP_HEADER_HEIGHT;
  return {
    x,
    y,
    width: Math.max(GROUP_MIN_WIDTH, maxX + GROUP_PADDING - x),
    height: Math.max(GROUP_MIN_HEIGHT, maxY + GROUP_PADDING - y),
  };
};

const withGroupSize = (group: Node, width: number, height: number): Node => ({
  ...group,
  style: { ...group.style, width, height },
  width,
  height,
});

export const createGroupNode = (id: string, rect: Rect, name: string): Node<GroupNodeData> => ({
  id,
  type: GROUP_NODE_TYPE,
  position: { x: rect.x, y: rect.y },
  style: { width: rect.width, height: rect.height },
  width: rect.width,
  height: rect.height,
  zIndex: GROUP_Z_INDEX,
  data: { name: name.trim() || DEFAULT_GROUP_NAME },
});

export const getGroupChildren = (nodes: Node[], groupId: string): Node[] =>
  nodes.filter((n) => getParentId(n) === groupId);

/**
 * React Flow v11 needs a parent before its children in the array, and draws same-z nodes in array
 * order. Putting every group first satisfies both. Returns the same array when already ordered.
 */
export const orderGroupsFirst = (nodes: Node[]): Node[] => {
  let seenNonGroup = false;
  let ordered = true;
  for (const node of nodes) {
    if (isGroupNode(node)) {
      if (seenNonGroup) {
        ordered = false;
        break;
      }
    } else {
      seenNonGroup = true;
    }
  }
  if (ordered) return nodes;
  return [...nodes.filter(isGroupNode), ...nodes.filter((n) => !isGroupNode(n))];
};

/**
 * Repairs grouping metadata so React Flow can never throw "Parent node not found": drops a
 * parent reference that points at a missing node or a non-group, and any parent on a group
 * (groups don't nest). Then orders groups first. Returns the same array when nothing changed.
 */
export const sanitizeGroupedNodes = (nodes: Node[]): Node[] => {
  const groupIds = new Set(nodes.filter(isGroupNode).map((n) => n.id));
  let changed = false;
  const repaired = nodes.map((node) => {
    const parentId = getParentId(node);
    const hasParentKeys = "parentId" in node || "parentNode" in node;
    if (!parentId && !hasParentKeys) return node;
    if (parentId && !isGroupNode(node) && groupIds.has(parentId)) return node;
    changed = true;
    return withoutParent(node);
  });
  return orderGroupsFirst(changed ? repaired : nodes);
};

/**
 * Nodes as handed to <ReactFlow>. React Flow 11.11's drag logic only skips a child whose parent is
 * also being dragged when the child uses the legacy `parentNode` field — with `parentId` a selected
 * child moves twice as far as its group. So state keeps `parentId` (the forward-compatible name we
 * persist) and the render layer translates it.
 */
export const toRenderableNodes = (nodes: Node[]): Node[] => {
  const sanitized = sanitizeGroupedNodes(nodes);
  if (!sanitized.some((n) => n.parentId)) return sanitized;
  return sanitized.map((node) => {
    if (!node.parentId) return node;
    const { parentId, ...rest } = node;
    return { ...rest, parentNode: parentId };
  });
};

/**
 * Wraps the given nodes in a new group sized to frame them. Groups in the selection are ignored
 * (no nesting); nodes already inside another group move to the new one. Child positions are
 * converted to be relative to the new group, so nothing moves on screen.
 */
export const groupNodes = (
  nodes: Node[],
  nodeIds: Iterable<string>,
  groupId: string,
  name: string = DEFAULT_GROUP_NAME
): Node[] => {
  const ids = new Set(nodeIds);
  const byId = indexById(nodes);
  const members = nodes.filter((n) => ids.has(n.id) && !isGroupNode(n));
  if (members.length === 0) return nodes;

  const frame = frameAround(members.map((n) => getAbsoluteRect(n, byId)));
  const group = createGroupNode(groupId, frame, name);
  const memberIds = new Set(members.map((n) => n.id));

  const next = nodes.map((node) => {
    if (!memberIds.has(node.id)) return node;
    const abs = getAbsolutePosition(node, byId);
    return {
      ...withParent(node, groupId),
      position: { x: abs.x - frame.x, y: abs.y - frame.y },
    };
  });
  return orderGroupsFirst([group, ...next]);
};

/** Moves a node into `groupId` (or to the root with null) without it moving on screen. */
export const reparentNode = (nodes: Node[], nodeId: string, groupId: string | null): Node[] => {
  const byId = indexById(nodes);
  const node = byId.get(nodeId);
  if (!node || isGroupNode(node)) return nodes;
  if ((getParentId(node) ?? null) === groupId) return nodes;
  const group = groupId ? byId.get(groupId) : undefined;
  if (groupId && !isGroupNode(group)) return nodes;

  const abs = getAbsolutePosition(node, byId);
  const moved = group
    ? {
        ...withParent(node, group.id),
        position: { x: abs.x - group.position.x, y: abs.y - group.position.y },
      }
    : { ...withoutParent(node), position: abs };
  return orderGroupsFirst(nodes.map((n) => (n.id === nodeId ? moved : n)));
};

/**
 * Resizes a group around its children. mode "grow" only ever enlarges it (used after a drag so a
 * user's manual sizing is respected); "fit" shrinks/grows to hug the children exactly. Growing up
 * or left moves the group's origin, so children are shifted by the opposite amount to stay put.
 */
export const fitGroupToChildren = (
  nodes: Node[],
  groupId: string,
  mode: "grow" | "fit" = "grow"
): Node[] => {
  const group = nodes.find((n) => n.id === groupId);
  if (!group || !isGroupNode(group)) return nodes;
  const children = getGroupChildren(nodes, groupId);
  if (children.length === 0) return nodes;

  // Work in group-relative space: the group's own top-left is (0, 0).
  const needed = frameAround(children.map((c) => ({ ...c.position, ...getNodeSize(c) })));
  const size = getNodeSize(group);
  let left = needed.x;
  let top = needed.y;
  let right = needed.x + needed.width;
  let bottom = needed.y + needed.height;
  if (mode === "grow") {
    left = Math.min(0, left);
    top = Math.min(0, top);
    right = Math.max(size.width, right);
    bottom = Math.max(size.height, bottom);
  }
  const width = Math.max(GROUP_MIN_WIDTH, right - left);
  const height = Math.max(GROUP_MIN_HEIGHT, bottom - top);
  if (left === 0 && top === 0 && width === size.width && height === size.height) return nodes;

  return nodes.map((node) => {
    if (node.id === groupId) {
      return withGroupSize(
        { ...node, position: { x: node.position.x + left, y: node.position.y + top } },
        width,
        height
      );
    }
    if (getParentId(node) === groupId && (left !== 0 || top !== 0)) {
      return { ...node, position: { x: node.position.x - left, y: node.position.y - top } };
    }
    return node;
  });
};

/**
 * Removes a group container and hands its children back to the canvas root at the same on-screen
 * position. Edges are untouched (they only ever reference the children).
 */
export const ungroupNodes = (nodes: Node[], groupId: string): Node[] => {
  const byId = indexById(nodes);
  const group = byId.get(groupId);
  if (!group || !isGroupNode(group)) return nodes;
  return nodes
    .filter((n) => n.id !== groupId)
    .map((node) =>
      getParentId(node) === groupId
        ? { ...withoutParent(node), position: getAbsolutePosition(node, byId) }
        : node
    );
};

/**
 * The group a dragged node should belong to: the smallest group whose rect contains the node's
 * centre. Groups in `excludeIds` (e.g. ones being dragged themselves) are skipped.
 */
export const findGroupAtNode = (
  nodes: Node[],
  node: Node,
  excludeIds: Set<string> = new Set()
): string | null => {
  const byId = indexById(nodes);
  const rect = getAbsoluteRect(byId.get(node.id) ?? node, byId);
  const cx = rect.x + rect.width / 2;
  const cy = rect.y + rect.height / 2;
  let best: { id: string; area: number } | null = null;
  for (const candidate of nodes) {
    if (!isGroupNode(candidate) || excludeIds.has(candidate.id)) continue;
    const g = getAbsoluteRect(candidate, byId);
    if (cx < g.x || cx > g.x + g.width || cy < g.y || cy > g.y + g.height) continue;
    const area = g.width * g.height;
    if (!best || area < best.area) best = { id: candidate.id, area };
  }
  return best?.id ?? null;
};

/**
 * After a drag ends: a dragged node whose centre now sits inside a group joins it, one dragged
 * outside its group leaves it, and every group that still holds a dragged node grows to contain it.
 * Nodes dragged together with their own group keep their relationship untouched.
 */
export const applyDragReparenting = (nodes: Node[], draggedIds: Iterable<string>): Node[] => {
  const dragged = new Set(draggedIds);
  let next = nodes;
  const touchedGroups = new Set<string>();
  for (const id of dragged) {
    const node = next.find((n) => n.id === id);
    if (!node || isGroupNode(node)) continue;
    const currentParent = getParentId(node) ?? null;
    if (currentParent && dragged.has(currentParent)) continue;
    const target = findGroupAtNode(next, node, dragged);
    if (target !== currentParent) next = reparentNode(next, id, target);
    if (target) touchedGroups.add(target);
  }
  for (const groupId of touchedGroups) next = fitGroupToChildren(next, groupId, "grow");
  return next;
};

/**
 * Re-frames every group around its children after an auto-arrange. `positions` holds the new
 * ROOT-LEVEL position of each executable node (auto-arrange works on a flat graph).
 */
export const applyLayoutWithGroups = (nodes: Node[], positions: Record<string, XY>): Node[] => {
  const byId = indexById(nodes);
  const absOf = (node: Node): XY => positions[node.id] ?? getAbsolutePosition(node, byId);

  const frames = new Map<string, Rect>();
  for (const group of nodes.filter(isGroupNode)) {
    const children = getGroupChildren(nodes, group.id);
    if (children.length === 0) continue;
    frames.set(group.id, frameAround(children.map((c) => ({ ...absOf(c), ...getNodeSize(c) }))));
  }

  return nodes.map((node) => {
    if (isGroupNode(node)) {
      const frame = frames.get(node.id);
      if (!frame) return node;
      return withGroupSize({ ...node, position: { x: frame.x, y: frame.y } }, frame.width, frame.height);
    }
    const parentId = getParentId(node);
    const frame = parentId ? frames.get(parentId) : undefined;
    if (!positions[node.id] && !frame) return node;
    const abs = absOf(node);
    return { ...node, position: frame ? { x: abs.x - frame.x, y: abs.y - frame.y } : abs };
  });
};

/**
 * The executable graph only: groups removed, their children converted to root-level positions.
 * Used by read-only renderers (execution graph, version diff) and by auto-arrange, none of which
 * know about groups.
 */
export const flattenGroups = (nodes: Node[]): Node[] => {
  if (!nodes.some((n) => isGroupNode(n) || getParentId(n))) return nodes;
  const byId = indexById(nodes);
  return nodes
    .filter((n) => !isGroupNode(n))
    .map((node) =>
      getParentId(node)
        ? { ...withoutParent(node), position: getAbsolutePosition(node, byId) }
        : node
    );
};

export interface GroupDeletionPlan {
  /** Group containers being deleted. */
  groupIds: string[];
  /** Executable nodes inside those groups. */
  memberIds: string[];
  /** Other selected, non-group nodes that aren't members of a deleted group. */
  otherNodeIds: string[];
  /** Explicitly selected edges. */
  edgeIds: string[];
}

export const planGroupDeletion = (
  nodes: Node[],
  groupIds: string[],
  selectedNodeIds: string[] = [],
  selectedEdgeIds: string[] = []
): GroupDeletionPlan => {
  const groups = new Set(groupIds);
  const memberIds = nodes
    .filter((n) => {
      const parentId = getParentId(n);
      return !!parentId && groups.has(parentId);
    })
    .map((n) => n.id);
  const members = new Set(memberIds);
  const byId = indexById(nodes);
  const otherNodeIds = selectedNodeIds.filter(
    (id) => !groups.has(id) && !members.has(id) && !!byId.get(id) && !isGroupNode(byId.get(id))
  );
  return { groupIds, memberIds, otherNodeIds, edgeIds: selectedEdgeIds };
};

/**
 * Applies a group deletion. "group-only" removes just the containers (children are ungrouped in
 * place) plus any other selected nodes/edges; "with-contents" also deletes the grouped nodes and
 * every edge attached to a deleted node.
 */
export const applyGroupDeletion = (
  nodes: Node[],
  edges: Edge[],
  plan: GroupDeletionPlan,
  mode: "group-only" | "with-contents"
): { nodes: Node[]; edges: Edge[] } => {
  let nextNodes = nodes;
  if (mode === "group-only") {
    for (const groupId of plan.groupIds) nextNodes = ungroupNodes(nextNodes, groupId);
  }
  const removed = new Set([
    ...plan.groupIds,
    ...plan.otherNodeIds,
    ...(mode === "with-contents" ? plan.memberIds : []),
  ]);
  const selectedEdges = new Set(plan.edgeIds);
  return {
    nodes: nextNodes.filter((n) => !removed.has(n.id)),
    edges: edges.filter(
      (e) => !selectedEdges.has(e.id) && !removed.has(e.source) && !removed.has(e.target)
    ),
  };
};

/**
 * Prepares clipboard nodes for pasting with fresh ids. A copied child keeps its group when that
 * group was copied too (remapped to the new copy) or still exists on the canvas; otherwise it is
 * pasted at the canvas root at its on-screen position. Only root-level nodes get the paste offset —
 * children already move with their (offset) group.
 */
export const prepareNodesForPaste = (
  copied: Node[],
  existing: Node[],
  idMap: Map<string, string>,
  offset: number
): Node[] => {
  const existingById = indexById(existing);
  const copiedById = indexById(copied);
  const pasted = copied.map((node) => {
    const { id, selected, position, positionAbsolute, ...rest } = node;
    void selected;
    const base = { ...withoutParent(rest as Node), id: idMap.get(id) ?? id, selected: false };
    const parentId = getParentId(node);

    if (parentId && idMap.has(parentId) && isGroupNode(copiedById.get(parentId))) {
      return { ...base, parentId: idMap.get(parentId)!, position: { ...position } };
    }
    if (parentId && isGroupNode(existingById.get(parentId))) {
      return {
        ...base,
        parentId,
        position: { x: position.x + offset, y: position.y + offset },
      };
    }
    const abs = parentId
      ? positionAbsolute ?? getAbsolutePosition(node, copiedById)
      : position;
    return { ...base, position: { x: abs.x + offset, y: abs.y + offset } };
  });
  return orderGroupsFirst(pasted as Node[]);
};
