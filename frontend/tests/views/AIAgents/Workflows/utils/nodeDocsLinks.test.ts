import { describe, it, expect } from "vitest";
import {
  NODE_DOCS_URLS,
  getNodeDocsUrl,
} from "@/views/AIAgents/Workflows/utils/nodeDocsLinks";

describe("getNodeDocsUrl", () => {
  it("returns the mapped URL for known node types", () => {
    expect(getNodeDocsUrl("templateNode")).toBe(
      "https://docs.genassist.ai/nodes/formatting/text-template"
    );
    expect(getNodeDocsUrl("agentNode")).toBe(
      "https://docs.genassist.ai/nodes/ai/ai-agent"
    );
    expect(getNodeDocsUrl("chatInputNode")).toBe(
      "https://docs.genassist.ai/nodes/io/start"
    );
  });

  it("resolves every entry in the map to its value under the docs base", () => {
    for (const [type, url] of Object.entries(NODE_DOCS_URLS)) {
      expect(getNodeDocsUrl(type)).toBe(url);
      expect(url.startsWith("https://docs.genassist.ai/nodes/")).toBe(true);
    }
  });

  it("returns undefined for unknown, empty, or missing node types", () => {
    expect(getNodeDocsUrl("noSuchNode")).toBeUndefined();
    expect(getNodeDocsUrl("")).toBeUndefined();
    expect(getNodeDocsUrl(undefined)).toBeUndefined();
  });
});
