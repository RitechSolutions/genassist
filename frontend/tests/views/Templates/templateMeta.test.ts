import { describe, it, expect } from "vitest";
import { Headphones, FileText, Mail, Sparkles } from "lucide-react";
import {
  CATEGORY_COLORS,
  categoryColor,
  iconFor,
  nodeLabel,
  capabilities,
} from "@/views/Templates/templateMeta";

const PRIMARY = "hsl(var(--primary))";

describe("categoryColor", () => {
  it("returns the brand primary for nullish/empty and support categories", () => {
    expect(categoryColor(undefined)).toBe(PRIMARY);
    expect(categoryColor(null)).toBe(PRIMARY);
    expect(categoryColor("")).toBe(PRIMARY);
    expect(categoryColor("customer support")).toBe(PRIMARY);
    expect(categoryColor("Support")).toBe(PRIMARY);
  });

  it("looks up known categories case- and whitespace-insensitively", () => {
    expect(categoryColor("  Knowledge  ")).toBe("#6366F1");
    expect(categoryColor("HR")).toBe("#8B5CF6");
    expect(categoryColor("human resources")).toBe("#8B5CF6");
    expect(categoryColor("productivity")).toBe("#F59E0B");
    expect(categoryColor("messaging")).toBe("#10B981");
    expect(categoryColor("sales")).toBe("#F43F5E");
  });

  it("falls back to the primary token for unknown categories", () => {
    expect(categoryColor("does-not-exist")).toBe(PRIMARY);
  });

  it("exposes the raw color map", () => {
    expect(CATEGORY_COLORS.knowledge).toBe("#6366F1");
    expect(CATEGORY_COLORS.support).toBe(PRIMARY);
  });
});

describe("iconFor", () => {
  it("returns the mapped icon component by name", () => {
    expect(iconFor("Headphones")).toBe(Headphones);
    expect(iconFor("Mail")).toBe(Mail);
    expect(iconFor("FileText")).toBe(FileText);
  });

  it("maps the FileUser alias to FileText", () => {
    expect(iconFor("FileUser")).toBe(FileText);
  });

  it("falls back to Sparkles for unknown / nullish names", () => {
    expect(iconFor(undefined)).toBe(Sparkles);
    expect(iconFor(null)).toBe(Sparkles);
    expect(iconFor("")).toBe(Sparkles);
    expect(iconFor("Nonexistent")).toBe(Sparkles);
  });
});

describe("nodeLabel", () => {
  it("maps known node types to human labels", () => {
    expect(nodeLabel("agentNode")).toBe("Agent");
    expect(nodeLabel("externalAgentNode")).toBe("Agent");
    expect(nodeLabel("voiceAgentNode")).toBe("Voice");
    expect(nodeLabel("ttsNode")).toBe("Voice");
    expect(nodeLabel("workflowExecutorNode")).toBe("Sub-flow");
  });

  it("strips the trailing 'Node' for unknown types", () => {
    expect(nodeLabel("someCustomNode")).toBe("someCustom");
    expect(nodeLabel("plainThing")).toBe("plainThing");
  });
});

describe("capabilities", () => {
  it("maps and de-duplicates labels preserving first-seen order", () => {
    expect(capabilities(["agentNode", "llmModelNode"])).toEqual(["Agent", "LLM"]);
    expect(capabilities(["agentNode", "externalAgentNode"])).toEqual(["Agent"]);
    expect(capabilities(["llmModelNode", "agentNode", "llmModelNode"])).toEqual(["LLM", "Agent"]);
    expect(capabilities(["ttsNode", "sttNode"])).toEqual(["Voice"]);
  });

  it("filters out structural/plumbing nodes when meaningful ones remain", () => {
    expect(capabilities(["agentNode", "chatInputNode", "llmModelNode"])).toEqual([
      "Agent",
      "LLM",
    ]);
  });

  it("falls back to the full set when only structural nodes are present", () => {
    expect(capabilities(["chatInputNode", "chatOutputNode"])).toEqual([
      "chatInput",
      "chatOutput",
    ]);
  });

  it("returns [] for an empty input", () => {
    expect(capabilities([])).toEqual([]);
  });
});
