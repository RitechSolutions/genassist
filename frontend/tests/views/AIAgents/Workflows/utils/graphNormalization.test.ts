import { describe, it, expect } from "vitest";
import { stripTransientGraphFields } from "@/views/AIAgents/Workflows/utils/graphNormalization";
import { Edge, Node } from "reactflow";

const mkNode = (over: Partial<Node> = {}): Node =>
  ({ id: "n", position: { x: 0, y: 0 }, data: {}, ...over }) as Node;

const mkEdge = (over: Partial<Edge> = {}): Edge =>
  ({ id: "e", source: "a", target: "b", ...over }) as Edge;

describe("stripTransientGraphFields", () => {
  it("removes transient UI fields from nodes but keeps the rest", () => {
    const node = mkNode({
      id: "x",
      type: "agentNode",
      selected: true,
      dragging: true,
      width: 100,
      height: 50,
      positionAbsolute: { x: 9, y: 9 },
      data: { name: "keep" },
    });

    const { nodes } = stripTransientGraphFields([node], []);
    const out = nodes[0];

    expect(out).toEqual({
      id: "x",
      type: "agentNode",
      position: { x: 0, y: 0 },
      data: { name: "keep" },
    });
    for (const field of ["selected", "dragging", "width", "height", "positionAbsolute"]) {
      expect(field in out).toBe(false);
    }
  });

  it("removes selected and className from edges but keeps the rest", () => {
    const edge = mkEdge({
      id: "e1",
      source: "a",
      target: "b",
      selected: true,
      className: "highlighted",
      data: { weight: 1 },
    });

    const { edges } = stripTransientGraphFields([], [edge]);
    const out = edges[0];

    expect(out).toEqual({
      id: "e1",
      source: "a",
      target: "b",
      data: { weight: 1 },
    });
    expect("selected" in out).toBe(false);
    expect("className" in out).toBe(false);
  });

  it("does not mutate the input nodes or edges", () => {
    const node = mkNode({ width: 100, selected: true });
    const edge = mkEdge({ className: "c", selected: true });

    stripTransientGraphFields([node], [edge]);

    expect(node.width).toBe(100);
    expect(node.selected).toBe(true);
    expect(edge.className).toBe("c");
    expect(edge.selected).toBe(true);
  });

  it("returns fresh arrays for empty input", () => {
    const result = stripTransientGraphFields([], []);
    expect(result).toEqual({ nodes: [], edges: [] });
  });
});
