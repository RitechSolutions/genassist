import { describe, it, expect } from "vitest";
import {
  computeAutoArrangeLayout,
  AutoArrangeNode,
  AutoArrangeEdge,
} from "@/views/AIAgents/Workflows/utils/autoArrangeLayout";

const n = (id: string, extra: Partial<AutoArrangeNode> = {}): AutoArrangeNode => ({
  id,
  ...extra,
});

const e = (
  source: string,
  target: string,
  extra: Partial<AutoArrangeEdge> = {}
): AutoArrangeEdge => ({ source, target, ...extra });

describe("computeAutoArrangeLayout", () => {
  it("returns an empty map for empty input", () => {
    expect(computeAutoArrangeLayout({ nodes: [], edges: [] })).toEqual({});
  });

  it("places a single node at the origin", () => {
    const pos = computeAutoArrangeLayout({ nodes: [n("a")], edges: [] });
    expect(pos.a).toEqual({ x: 0, y: 0 });
  });

  it("lays a linear chain out left-to-right on a shared line", () => {
    const pos = computeAutoArrangeLayout({
      nodes: [n("a"), n("b"), n("c")],
      edges: [e("a", "b"), e("b", "c")],
    });
    expect(pos.a.x).toBeLessThan(pos.b.x);
    expect(pos.b.x).toBeLessThan(pos.c.x);
    expect(pos.a.y).toBe(pos.b.y);
    expect(pos.b.y).toBe(pos.c.y);
  });

  it("normalizes so the top-left of the graph is the origin", () => {
    const pos = computeAutoArrangeLayout({
      nodes: [n("a"), n("b"), n("c"), n("d")],
      edges: [e("a", "b"), e("a", "c"), e("b", "d"), e("c", "d")],
    });
    const xs = Object.values(pos).map((p) => p.x);
    const ys = Object.values(pos).map((p) => p.y);
    expect(Math.min(...xs)).toBe(0);
    expect(Math.min(...ys)).toBe(0);
  });

  it("stacks the branches of a split vertically past the splitter", () => {
    const pos = computeAutoArrangeLayout({
      nodes: [n("a"), n("b"), n("c")],
      edges: [e("a", "b"), e("a", "c")],
    });
    expect(pos.a.x).toBeLessThan(pos.b.x);
    // branches share a vertical axis (stacked on top of one another)
    expect(pos.b.x).toBeCloseTo(pos.c.x, 5);
    // and are separated vertically
    expect(pos.b.y).not.toBe(pos.c.y);
  });

  it("orders sibling branches by target id when handles are absent", () => {
    const pos = computeAutoArrangeLayout({
      nodes: [n("a"), n("b"), n("c")],
      edges: [e("a", "c"), e("a", "b")],
    });
    // 'b' sorts before 'c', so it takes the upper (smaller y) line
    expect(pos.b.y).toBeLessThan(pos.c.y);
  });

  it("places a merger node to the right of the branches it closes (diamond)", () => {
    const pos = computeAutoArrangeLayout({
      nodes: [n("a"), n("b"), n("c"), n("d")],
      edges: [e("a", "b"), e("a", "c"), e("b", "d"), e("c", "d")],
    });
    expect(pos.a.x).toBeLessThan(pos.b.x);
    expect(pos.d.x).toBeGreaterThan(pos.b.x);
    expect(pos.d.x).toBeGreaterThan(pos.c.x);
    expect(pos.b.y).not.toBe(pos.c.y);
  });

  it("hangs an agent's tools below it via top/bottom tool handles", () => {
    const agent = n("ag", {
      data: {
        handlers: [
          { id: "ag-tools", type: "target", position: "bottom", compatibility: "tools" },
        ],
      },
    });
    const pos = computeAutoArrangeLayout({
      nodes: [agent, n("tool")],
      edges: [e("tool", "ag", { targetHandle: "ag-tools" })],
    });
    expect(pos.ag).toBeDefined();
    expect(pos.tool).toBeDefined();
    // the tool hangs below the agent
    expect(pos.tool.y).toBeGreaterThan(pos.ag.y);
  });

  it("reserves more horizontal room after a wider node", () => {
    const narrow = computeAutoArrangeLayout({
      nodes: [n("a"), n("b")],
      edges: [e("a", "b")],
    });
    const wide = computeAutoArrangeLayout({
      nodes: [n("a", { width: 800 }), n("b")],
      edges: [e("a", "b")],
    });
    expect(wide.b.x - wide.a.x).toBeGreaterThan(narrow.b.x - narrow.a.x);
  });

  it("ignores self-loops and edges to unknown nodes", () => {
    const pos = computeAutoArrangeLayout({
      nodes: [n("a"), n("b")],
      edges: [e("a", "a"), e("a", "ghost"), e("a", "b")],
    });
    expect(Object.keys(pos).sort()).toEqual(["a", "b"]);
    expect(pos.a.x).toBeLessThan(pos.b.x);
  });

  it("does not throw on a cycle and still positions every node", () => {
    const pos = computeAutoArrangeLayout({
      nodes: [n("a"), n("b"), n("c")],
      edges: [e("a", "b"), e("b", "c"), e("c", "a")],
    });
    expect(Object.keys(pos).sort()).toEqual(["a", "b", "c"]);
  });

  it("positions every node across disconnected components", () => {
    const pos = computeAutoArrangeLayout({
      nodes: [n("a"), n("b"), n("c"), n("d")],
      edges: [e("a", "b"), e("c", "d")],
    });
    expect(Object.keys(pos).sort()).toEqual(["a", "b", "c", "d"]);
  });

  it("is deterministic for the same input", () => {
    const input = {
      nodes: [n("a"), n("b"), n("c"), n("d")],
      edges: [e("a", "b"), e("a", "c"), e("b", "d"), e("c", "d")],
    };
    expect(computeAutoArrangeLayout(input)).toEqual(computeAutoArrangeLayout(input));
  });
});
