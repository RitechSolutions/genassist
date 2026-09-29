import { describe, it, expect } from "vitest";
import type { Edge, Node } from "reactflow";
import {
  GROUP_HEADER_HEIGHT,
  GROUP_NODE_TYPE,
  GROUP_PADDING,
  GROUP_Z_INDEX,
  applyDragReparenting,
  applyGroupDeletion,
  applyLayoutWithGroups,
  createGroupNode,
  findGroupAtNode,
  fitGroupToChildren,
  flattenGroups,
  getAbsolutePosition,
  getParentId,
  groupNodes,
  isGroupNode,
  orderGroupsFirst,
  planGroupDeletion,
  prepareNodesForPaste,
  reparentNode,
  sanitizeGroupedNodes,
  toRenderableNodes,
  ungroupNodes,
} from "@/views/AIAgents/Workflows/utils/nodeGroups";

const node = (id: string, x: number, y: number, over: Partial<Node> = {}): Node =>
  ({
    id,
    type: "templateNode",
    position: { x, y },
    width: 100,
    height: 50,
    data: { name: id },
    ...over,
  }) as Node;

const edge = (id: string, source: string, target: string): Edge => ({ id, source, target });

const byId = (nodes: Node[]) => new Map(nodes.map((n) => [n.id, n]));
const abs = (nodes: Node[], id: string) => getAbsolutePosition(byId(nodes).get(id)!, byId(nodes));
const find = (nodes: Node[], id: string) => nodes.find((n) => n.id === id)!;

// A group at (0,0) sized 400x300 holding A at (50,100) and B at (200,100).
const grouped = (): Node[] => [
  createGroupNode("g", { x: 0, y: 0, width: 400, height: 300 }, "Payments"),
  node("a", 50, 100, { parentId: "g" }),
  node("b", 200, 100, { parentId: "g" }),
  node("c", 1000, 1000),
];

describe("groupNodes", () => {
  it("frames the selection with padding + header and keeps every node where it was on screen", () => {
    const nodes = [node("a", 100, 200), node("b", 400, 260), node("c", 900, 900)];
    const next = groupNodes(nodes, ["a", "b"], "g", "Payment Processing");

    const group = find(next, "g");
    expect(next[0].id).toBe("g"); // parent before children
    expect(group.type).toBe(GROUP_NODE_TYPE);
    expect(group.zIndex).toBe(GROUP_Z_INDEX);
    expect(group.data.name).toBe("Payment Processing");
    expect(group.position).toEqual({
      x: 100 - GROUP_PADDING,
      y: 200 - GROUP_PADDING - GROUP_HEADER_HEIGHT,
    });
    expect(group.style).toEqual({
      width: 400 + 100 - 100 + 2 * GROUP_PADDING,
      height: 260 + 50 - 200 + 2 * GROUP_PADDING + GROUP_HEADER_HEIGHT,
    });

    expect(find(next, "a").parentId).toBe("g");
    expect(find(next, "b").parentId).toBe("g");
    expect(find(next, "c").parentId).toBeUndefined();
    expect(abs(next, "a")).toEqual({ x: 100, y: 200 });
    expect(abs(next, "b")).toEqual({ x: 400, y: 260 });
    expect(find(next, "c")).toBe(nodes[2]); // untouched
  });

  it("falls back to 'Untitled Group' and ignores groups in the selection (no nesting)", () => {
    const nodes = grouped();
    const next = groupNodes(nodes, ["g", "c"], "g2", "   ");
    expect(find(next, "g2").data.name).toBe("Untitled Group");
    expect(getParentId(find(next, "g"))).toBeUndefined();
    expect(find(next, "c").parentId).toBe("g2");
  });

  it("moves nodes out of their old group without them jumping", () => {
    const nodes = grouped();
    const next = groupNodes(nodes, ["a", "c"], "g2");
    expect(find(next, "a").parentId).toBe("g2");
    expect(abs(next, "a")).toEqual({ x: 50, y: 100 });
    expect(abs(next, "c")).toEqual({ x: 1000, y: 1000 });
    expect(find(next, "b").parentId).toBe("g");
  });

  it("returns the input unchanged when nothing groupable is selected", () => {
    const nodes = grouped();
    expect(groupNodes(nodes, ["g"], "g2")).toBe(nodes);
  });
});

describe("ungroupNodes", () => {
  it("removes the container and converts children back to root positions", () => {
    const nodes = grouped().map((n) => (n.id === "g" ? { ...n, position: { x: 300, y: 500 } } : n));
    const next = ungroupNodes(nodes, "g");
    expect(next.map((n) => n.id)).toEqual(["a", "b", "c"]);
    expect(find(next, "a").position).toEqual({ x: 350, y: 600 });
    expect(find(next, "b").position).toEqual({ x: 500, y: 600 });
    expect(next.some((n) => "parentId" in n)).toBe(false);
  });
});

describe("reparentNode", () => {
  it("round-trips a node into and out of a group without moving it", () => {
    const nodes = grouped().map((n) => (n.id === "g" ? { ...n, position: { x: 900, y: 900 } } : n));
    const inside = reparentNode(nodes, "c", "g");
    expect(find(inside, "c").parentId).toBe("g");
    expect(find(inside, "c").position).toEqual({ x: 100, y: 100 });
    expect(abs(inside, "c")).toEqual({ x: 1000, y: 1000 });

    const outside = reparentNode(inside, "c", null);
    expect(find(outside, "c").parentId).toBeUndefined();
    expect(find(outside, "c").position).toEqual({ x: 1000, y: 1000 });
  });

  it("refuses to parent a group or to use a non-group as parent", () => {
    const nodes = grouped();
    expect(reparentNode(nodes, "g", "g")).toBe(nodes);
    expect(reparentNode(nodes, "c", "a")).toBe(nodes);
  });
});

describe("fitGroupToChildren", () => {
  it("grow mode enlarges right/bottom only as needed", () => {
    const nodes = grouped().map((n) => (n.id === "b" ? { ...n, position: { x: 500, y: 100 } } : n));
    const next = fitGroupToChildren(nodes, "g", "grow");
    expect(find(next, "g").style).toMatchObject({ width: 500 + 100 + GROUP_PADDING, height: 300 });
    expect(find(next, "g").position).toEqual({ x: 0, y: 0 });
  });

  it("growing up/left moves the origin and shifts children so nothing moves on screen", () => {
    const nodes = grouped().map((n) => (n.id === "a" ? { ...n, position: { x: -60, y: 10 } } : n));
    const before = { a: abs(nodes, "a"), b: abs(nodes, "b") };
    const next = fitGroupToChildren(nodes, "g", "grow");
    const group = find(next, "g");
    expect(group.position).toEqual({
      x: -60 - GROUP_PADDING,
      y: 10 - GROUP_PADDING - GROUP_HEADER_HEIGHT,
    });
    expect(abs(next, "a")).toEqual(before.a);
    expect(abs(next, "b")).toEqual(before.b);
  });

  it("fit mode hugs the children and is a no-op when already fitted", () => {
    const next = fitGroupToChildren(grouped(), "g", "fit");
    const fitted = find(next, "g");
    expect(fitted.style).toMatchObject({
      width: 300 - 50 + 2 * GROUP_PADDING,
      height: 50 + 2 * GROUP_PADDING + GROUP_HEADER_HEIGHT,
    });
    expect(abs(next, "a")).toEqual({ x: 50, y: 100 });
    expect(fitGroupToChildren(next, "g", "fit")).toBe(next);
  });

  it("grow mode returns the same array when children already fit", () => {
    const nodes = grouped();
    expect(fitGroupToChildren(nodes, "g", "grow")).toBe(nodes);
  });
});

describe("drag reparenting", () => {
  it("finds the smallest group containing the node's centre", () => {
    const nodes = [
      createGroupNode("big", { x: 0, y: 0, width: 1000, height: 1000 }, "Big"),
      createGroupNode("small", { x: 100, y: 100, width: 300, height: 300 }, "Small"),
      node("n", 150, 150),
    ];
    expect(findGroupAtNode(nodes, find(nodes, "n"))).toBe("small");
    expect(findGroupAtNode(nodes, find(nodes, "n"), new Set(["small"]))).toBe("big");
  });

  it("joins a group when dropped inside it, leaves it when dropped outside", () => {
    const joined = applyDragReparenting(
      grouped().map((n) => (n.id === "c" ? { ...n, position: { x: 150, y: 200 } } : n)),
      ["c"]
    );
    expect(find(joined, "c").parentId).toBe("g");
    expect(abs(joined, "c")).toEqual({ x: 150, y: 200 });

    const left = applyDragReparenting(
      joined.map((n) => (n.id === "a" ? { ...n, position: { x: 2000, y: 2000 } } : n)),
      ["a"]
    );
    expect(find(left, "a").parentId).toBeUndefined();
    expect(find(left, "a").position).toEqual({ x: 2000, y: 2000 });
  });

  it("keeps a child in its group when both were dragged together", () => {
    const nodes = grouped();
    expect(applyDragReparenting(nodes, ["g", "a"])).toBe(nodes);
  });

  it("grows the group when a child is dragged partly past its edge", () => {
    const nodes = grouped().map((n) => (n.id === "b" ? { ...n, position: { x: 340, y: 100 } } : n));
    const next = applyDragReparenting(nodes, ["b"]);
    expect(find(next, "b").parentId).toBe("g");
    expect((find(next, "g").style as { width: number }).width).toBe(340 + 100 + GROUP_PADDING);
  });
});

describe("render/persistence safety", () => {
  it("orders groups before other nodes, reusing the array when already ordered", () => {
    const ordered = grouped();
    expect(orderGroupsFirst(ordered)).toBe(ordered);
    const shuffled = [ordered[1], ordered[0], ordered[3], ordered[2]];
    expect(orderGroupsFirst(shuffled).map((n) => n.id)).toEqual(["g", "a", "c", "b"]);
  });

  it("drops dangling / invalid parent references", () => {
    const nodes = [
      node("x", 0, 0, { parentId: "missing" }),
      node("y", 0, 0, { parentId: "x" }), // parent isn't a group
      { ...createGroupNode("g", { x: 0, y: 0, width: 300, height: 200 }, "G"), parentId: "g2" },
      createGroupNode("g2", { x: 0, y: 0, width: 300, height: 200 }, "G2"),
    ];
    const next = sanitizeGroupedNodes(nodes);
    expect(next.map((n) => getParentId(n))).toEqual([undefined, undefined, undefined, undefined]);
    expect(next.slice(0, 2).every(isGroupNode)).toBe(true);
    expect(sanitizeGroupedNodes(next)).toBe(next);
  });

  it("maps parentId to React Flow v11's parentNode for rendering only", () => {
    const nodes = grouped();
    const rendered = toRenderableNodes(nodes);
    expect(find(rendered, "a").parentNode).toBe("g");
    expect(find(rendered, "a").parentId).toBeUndefined();
    expect(find(nodes, "a").parentId).toBe("g"); // state untouched
    const plain = [node("p", 0, 0)];
    expect(toRenderableNodes(plain)).toBe(plain);
  });

  it("flattens groups away for read-only views, with root positions", () => {
    const nodes = grouped().map((n) => (n.id === "g" ? { ...n, position: { x: 10, y: 20 } } : n));
    const flat = flattenGroups(nodes);
    expect(flat.map((n) => n.id)).toEqual(["a", "b", "c"]);
    expect(find(flat, "a").position).toEqual({ x: 60, y: 120 });
    expect(flat.some((n) => getParentId(n))).toBe(false);
    const plain = [node("p", 0, 0)];
    expect(flattenGroups(plain)).toBe(plain);
  });
});

describe("applyLayoutWithGroups", () => {
  it("places children at the arranged root positions and re-frames their group", () => {
    const next = applyLayoutWithGroups(grouped(), {
      a: { x: 1000, y: 0 },
      b: { x: 1300, y: 0 },
      c: { x: 0, y: 0 },
    });
    expect(abs(next, "a")).toEqual({ x: 1000, y: 0 });
    expect(abs(next, "b")).toEqual({ x: 1300, y: 0 });
    expect(find(next, "c").position).toEqual({ x: 0, y: 0 });
    expect(find(next, "g").position).toEqual({
      x: 1000 - GROUP_PADDING,
      y: -GROUP_PADDING - GROUP_HEADER_HEIGHT,
    });
  });
});

describe("group deletion", () => {
  const edges = [edge("e1", "a", "b"), edge("e2", "b", "c"), edge("e3", "c", "d")];
  const nodes = [...grouped(), node("d", 1200, 1000)];

  it("plans members separately from other selected nodes", () => {
    const plan = planGroupDeletion(nodes, ["g"], ["g", "a", "d"], ["e3"]);
    expect(plan).toEqual({ groupIds: ["g"], memberIds: ["a", "b"], otherNodeIds: ["d"], edgeIds: ["e3"] });
  });

  it("group-only keeps the members in place along with their edges", () => {
    const plan = planGroupDeletion(nodes, ["g"]);
    const result = applyGroupDeletion(nodes, edges, plan, "group-only");
    expect(result.nodes.map((n) => n.id)).toEqual(["a", "b", "c", "d"]);
    expect(find(result.nodes, "a").position).toEqual({ x: 50, y: 100 });
    expect(result.edges).toEqual(edges);
  });

  it("with-contents removes the members and every edge touching them", () => {
    const plan = planGroupDeletion(nodes, ["g"], ["g", "d"]);
    const result = applyGroupDeletion(nodes, edges, plan, "with-contents");
    expect(result.nodes.map((n) => n.id)).toEqual(["c"]);
    expect(result.edges).toEqual([]);
  });
});

describe("prepareNodesForPaste", () => {
  it("remaps a copied group and keeps its children relative", () => {
    const nodes = grouped();
    const idMap = new Map([
      ["g", "g-new"],
      ["a", "a-new"],
    ]);
    const pasted = prepareNodesForPaste([find(nodes, "a"), find(nodes, "g")], nodes, idMap, 40);
    expect(pasted.map((n) => n.id)).toEqual(["g-new", "a-new"]);
    expect(find(pasted, "g-new").position).toEqual({ x: 40, y: 40 });
    expect(find(pasted, "a-new")).toMatchObject({ parentId: "g-new", position: { x: 50, y: 100 } });
  });

  it("pastes a lone child into its still-existing group, or at root when the group is gone", () => {
    const nodes = grouped();
    const idMap = new Map([["a", "a2"]]);
    const same = prepareNodesForPaste([find(nodes, "a")], nodes, idMap, 40);
    expect(same[0]).toMatchObject({ parentId: "g", position: { x: 90, y: 140 } });

    const copiedFromStore = { ...find(nodes, "a"), positionAbsolute: { x: 350, y: 400 } };
    const orphan = prepareNodesForPaste([copiedFromStore], [], idMap, 40);
    expect(getParentId(orphan[0])).toBeUndefined();
    expect(orphan[0].position).toEqual({ x: 390, y: 440 });
  });
});
