import { describe, it, expect } from "vitest";
import { Node } from "reactflow";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import {
  getNodeDisplayName,
  buildDeleteConfirmation,
} from "@/views/AIAgents/Workflows/utils/nodeDeletion";

const node = (type: string, data: Record<string, unknown> = {}): Node => ({
  id: "n1",
  type,
  position: { x: 0, y: 0 },
  data,
});

describe("getNodeDisplayName", () => {
  it("prefers the node's own name", () => {
    expect(getNodeDisplayName(node("modelNode", { name: "Summarizer" }))).toBe(
      "Summarizer"
    );
  });

  it("falls back to the registry label", () => {
    nodeRegistry.register({
      type: "testOnlyNode",
      label: "Test Only",
      category: "test",
    } as never);
    expect(getNodeDisplayName(node("testOnlyNode"))).toBe("Test Only");
  });

  it("falls back to 'node' for an unknown type", () => {
    expect(getNodeDisplayName(node("doesNotExist"))).toBe("node");
  });
});

describe("buildDeleteConfirmation", () => {
  it("names a single node and leaves the default sentence in place", () => {
    expect(
      buildDeleteConfirmation([node("modelNode", { name: "Summarizer" })])
    ).toEqual({ itemName: "Summarizer" });
  });

  it("counts a multi-selection instead of naming it", () => {
    expect(buildDeleteConfirmation([node("a"), node("b"), node("c")])).toEqual({
      itemName: "",
      description:
        "This action cannot be undone. This will permanently delete 3 nodes.",
    });
  });
});
