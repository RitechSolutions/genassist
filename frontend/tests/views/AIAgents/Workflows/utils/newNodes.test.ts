import { describe, it, expect } from "vitest";
import { NEW_NODE_TYPES, isNewNode } from "@/views/AIAgents/Workflows/utils/newNodes";

describe("NEW_NODE_TYPES", () => {
  it("contains exactly the five flagged node types", () => {
    expect(NEW_NODE_TYPES).toEqual(
      new Set([
        "nlpNode",
        "webScraperNode",
        "htmlToImageNode",
        "salesforceCaseNode",
        "subAgentNode",
      ])
    );
  });
});

describe("isNewNode", () => {
  it("returns true for each flagged node type", () => {
    for (const type of NEW_NODE_TYPES) {
      expect(isNewNode(type)).toBe(true);
    }
  });

  it("returns false for unknown or empty types", () => {
    expect(isNewNode("agentNode")).toBe(false);
    expect(isNewNode("chatInputNode")).toBe(false);
    expect(isNewNode("")).toBe(false);
  });
});
