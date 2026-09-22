import { describe, it, expect } from "vitest";
import { Edge } from "reactflow";
import { edgesOnRemovedHandles } from "@/views/AIAgents/Workflows/utils/handleEdges";
import { NodeHandler } from "@/views/AIAgents/Workflows/types/nodes";

const handle = (id: string, type: "source" | "target" = "source"): NodeHandler => ({
  id,
  type,
  position: type === "source" ? "right" : "left",
  compatibility: "any",
});
const edge = (id: string, source: string, sourceHandle: string | null, target: string, targetHandle: string | null): Edge => ({
  id,
  source,
  sourceHandle,
  target,
  targetHandle,
});

const before = [handle("input", "target"), handle("output_case_1"), handle("output_case_2"), handle("output_default")];
const after = [handle("input", "target"), handle("output_case_2"), handle("output_default")];

describe("edgesOnRemovedHandles", () => {
  const edges = [
    edge("in", "start", "output", "sw", "input"),
    edge("c1", "sw", "output_case_1", "a", "input"),
    edge("c2", "sw", "output_case_2", "b", "input"),
    edge("other", "x", "output_case_1", "y", "input"),
  ];

  it("returns only this node's edges on handles the update removed", () => {
    expect(edgesOnRemovedHandles(edges, "sw", before, after).map((e) => e.id)).toEqual(["c1"]);
  });

  it("returns nothing when no handle was removed", () => {
    expect(edgesOnRemovedHandles(edges, "sw", before, before)).toEqual([]);
    expect(edgesOnRemovedHandles(edges, "sw", undefined, after)).toEqual([]);
  });

  it("covers removed target handles too", () => {
    const withoutInput = before.filter((h) => h.id !== "input");
    expect(edgesOnRemovedHandles(edges, "sw", before, withoutInput).map((e) => e.id)).toEqual(["in"]);
  });

  it("leaves edges on handles the node never declared", () => {
    const legacy = [...edges, edge("legacy", "sw", "output_legacy", "z", "input"), edge("bare", "sw", null, "z", "input")];
    expect(edgesOnRemovedHandles(legacy, "sw", before, after).map((e) => e.id)).toEqual(["c1"]);
  });
});
