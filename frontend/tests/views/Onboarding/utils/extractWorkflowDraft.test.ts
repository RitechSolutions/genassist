import { describe, it, expect } from "vitest";
import {
  isWorkflowDraft,
  hasWorkflowReadySignal,
  stripWorkflowTags,
  extractWorkflowDraftFromText,
} from "@/views/Onboarding/utils/extractWorkflowDraft";

const node = (over: Record<string, unknown> = {}) => ({
  uniqueId: "n1",
  node_name: "Start",
  function_of_node: "input",
  ...over,
});

describe("isWorkflowDraft", () => {
  it("accepts a { workflow: [...] } object with valid nodes", () => {
    expect(isWorkflowDraft({ workflow: [node()] })).toBe(true);
  });

  it("accepts a bare non-empty array of valid nodes", () => {
    expect(isWorkflowDraft([node()])).toBe(true);
  });

  it("accepts nodes with next_node_id null or string", () => {
    expect(isWorkflowDraft([node({ next_node_id: null })])).toBe(true);
    expect(isWorkflowDraft([node({ next_node_id: "n2" })])).toBe(true);
  });

  it("rejects empty containers", () => {
    expect(isWorkflowDraft({ workflow: [] })).toBe(false);
    expect(isWorkflowDraft([])).toBe(false);
  });

  it("rejects nodes missing required non-empty string fields", () => {
    expect(isWorkflowDraft([node({ uniqueId: "" })])).toBe(false);
    expect(isWorkflowDraft([{ uniqueId: "n1", node_name: "S" }])).toBe(false); // no function_of_node
    expect(isWorkflowDraft([node({ node_name: "   " })])).toBe(false);
  });

  it("rejects nodes with a non-string, non-null next_node_id", () => {
    expect(isWorkflowDraft([node({ next_node_id: 5 })])).toBe(false);
  });

  it("rejects non-object / non-array primitives", () => {
    expect(isWorkflowDraft(null)).toBe(false);
    expect(isWorkflowDraft("string")).toBe(false);
    expect(isWorkflowDraft({ workflow: "notarray" })).toBe(false);
    expect(isWorkflowDraft({ foo: 1 })).toBe(false);
  });

  it("rejects when the workflow array contains any invalid node", () => {
    expect(isWorkflowDraft({ workflow: [node(), { uniqueId: "n2" }] })).toBe(false);
  });
});

describe("hasWorkflowReadySignal", () => {
  it("matches self-closing and spaced variants", () => {
    expect(hasWorkflowReadySignal("<WORKFLOW_READY/>")).toBe(true);
    expect(hasWorkflowReadySignal("<WORKFLOW_READY />")).toBe(true);
    expect(hasWorkflowReadySignal("<WORKFLOW_READY>")).toBe(true);
  });

  it("is case-insensitive and matches when embedded in text", () => {
    expect(hasWorkflowReadySignal("<workflow_ready/>")).toBe(true);
    expect(hasWorkflowReadySignal("done <WORKFLOW_READY/> now")).toBe(true);
  });

  it("returns false when the tag is absent or malformed", () => {
    expect(hasWorkflowReadySignal("no signal here")).toBe(false);
    expect(hasWorkflowReadySignal("<WORKFLOW_READYX>")).toBe(false);
  });
});

describe("stripWorkflowTags", () => {
  it("removes <WORKFLOW_JSON> blocks", () => {
    expect(stripWorkflowTags("Hello <WORKFLOW_JSON>{...}</WORKFLOW_JSON> World")).toBe(
      "Hello  World"
    );
  });

  it("removes the ready signal", () => {
    expect(stripWorkflowTags("<WORKFLOW_READY/>Done")).toBe("Done");
    expect(stripWorkflowTags("<WORKFLOW_READY />")).toBe("");
  });

  it("removes fenced code blocks that contain a workflow", () => {
    const text = 'Before ```json\n{"workflow":[]}\n``` After';
    expect(stripWorkflowTags(text)).toBe("Before  After");
  });

  it("trims and leaves untagged text otherwise unchanged", () => {
    expect(stripWorkflowTags("  hello  ")).toBe("hello");
  });
});

describe("extractWorkflowDraftFromText", () => {
  const validNode = node();

  it("returns null for empty / whitespace-only text", () => {
    expect(extractWorkflowDraftFromText("")).toBeNull();
    expect(extractWorkflowDraftFromText("   ")).toBeNull();
  });

  it("returns null when no valid workflow JSON is present", () => {
    expect(extractWorkflowDraftFromText("just some prose")).toBeNull();
    expect(extractWorkflowDraftFromText('{"foo":1}')).toBeNull();
  });

  it("extracts a draft from a fenced json block and reports the ready signal", () => {
    const text = [
      "Here is the workflow:",
      "```json",
      JSON.stringify({ workflow: [validNode] }),
      "```",
      "<WORKFLOW_READY/>",
    ].join("\n");
    const result = extractWorkflowDraftFromText(text);
    expect(result).not.toBeNull();
    expect(result?.isReady).toBe(true);
    expect(result?.parsed).toEqual({ workflow: [validNode] });
    expect(result?.raw).toBe(JSON.stringify({ workflow: [validNode] }));
  });

  it("extracts a draft from a <WORKFLOW_JSON> tagged block", () => {
    const text = `intro <WORKFLOW_JSON>${JSON.stringify({ workflow: [validNode] })}</WORKFLOW_JSON>`;
    const result = extractWorkflowDraftFromText(text);
    expect(result?.parsed).toEqual({ workflow: [validNode] });
    expect(result?.isReady).toBe(false);
  });

  it("extracts an inline object via balanced-brace scanning", () => {
    const text = `The result: ${JSON.stringify({ workflow: [validNode] })} done`;
    const result = extractWorkflowDraftFromText(text);
    expect(result?.parsed).toEqual({ workflow: [validNode] });
  });

  it("normalizes a bare array draft into { workflow: [...] } for raw/parsed", () => {
    const text = `prefix ${JSON.stringify([validNode])} suffix`;
    const result = extractWorkflowDraftFromText(text);
    expect(result?.parsed).toEqual({ workflow: [validNode] });
    expect(result?.raw).toBe(JSON.stringify({ workflow: [validNode] }));
  });
});
