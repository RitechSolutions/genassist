import { describe, expect, it } from "vitest";
import { nodeTypeLabel } from "@/helpers/nodeTypeLabel";

describe("nodeTypeLabel", () => {
  it("returns the curated label for known node types", () => {
    expect(nodeTypeLabel("agentNode")).toBe("AI Agent");
    expect(nodeTypeLabel("chatInputNode")).toBe("Start");
    expect(nodeTypeLabel("routerNode")).toBe("Conditional Router");
    expect(nodeTypeLabel("gmailNode")).toBe("Email Sender");
  });

  it("derives a label from camelCase for unknown types", () => {
    expect(nodeTypeLabel("fooNode")).toBe("Foo");
    expect(nodeTypeLabel("myCoolNode")).toBe("My Cool");
    expect(nodeTypeLabel("customThingNode")).toBe("Custom Thing");
  });
});
