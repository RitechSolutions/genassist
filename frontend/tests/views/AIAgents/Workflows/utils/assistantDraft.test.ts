import { describe, it, expect } from "vitest";
import { Edge, Node } from "reactflow";
import {
  changeKind,
  changesAffectLayout,
  clearAiChanges,
  markAiChanges,
  mentionedNodeIds,
  parseSlashCommand,
  splitNodeMentions,
  mergeDraftNodes,
  reportableIssues,
  serializeCanvasForDraft,
} from "@/views/AIAgents/Workflows/utils/assistantDraft";
import type { BuilderDraft, BuilderIssue } from "@/services/workflowBuilder";

const node = (id: string, data: Record<string, unknown> = {}, extra: Partial<Node> = {}): Node => ({
  id,
  type: "agentNode",
  position: { x: 10, y: 20 },
  data: { name: id, ...data },
  ...extra,
});

describe("serializeCanvasForDraft", () => {
  it("drops callbacks and keeps everything else", () => {
    const nodes = [node("a", { updateNodeData: () => undefined, systemPrompt: "hi" })];
    const edges: Edge[] = [{ id: "e", source: "a", target: "b", sourceHandle: "output" }];

    const snapshot = serializeCanvasForDraft(nodes, edges, "a");

    expect(snapshot.nodes[0]).toEqual({
      id: "a",
      type: "agentNode",
      position: { x: 10, y: 20 },
      data: { name: "a", systemPrompt: "hi" },
    });
    expect(snapshot.edges).toEqual(edges);
    expect(snapshot.selected_node_id).toBe("a");
  });

  it("sends null when nothing is selected", () => {
    expect(serializeCanvasForDraft([], []).selected_node_id).toBeNull();
  });
});

describe("mergeDraftNodes", () => {
  it("takes data from the draft but keeps where the user put the node", () => {
    const current = [
      node("a", { systemPrompt: "old" }, { position: { x: 500, y: 600 }, selected: true, parentId: "g" }),
    ];
    const draft = [node("a", { systemPrompt: "new" }, { position: { x: 0, y: 0 } })];

    const [merged] = mergeDraftNodes(current, draft);

    expect(merged.data.systemPrompt).toBe("new");
    expect(merged.position).toEqual({ x: 500, y: 600 });
    expect(merged.selected).toBe(true);
    expect(merged.parentId).toBe("g");
  });

  it("adds new nodes as the draft placed them and drops removed ones", () => {
    const current = [node("a"), node("gone")];
    const draft = [node("a"), node("new", {}, { position: { x: 360, y: 20 } })];

    const merged = mergeDraftNodes(current, draft);

    expect(merged.map((n) => n.id)).toEqual(["a", "new"]);
    expect(merged[1].position).toEqual({ x: 360, y: 20 });
  });
});

describe("reportableIssues", () => {
  const issue = (overrides: Partial<BuilderIssue>): BuilderIssue => ({
    code: "dead_end",
    severity: "error",
    message: "m",
    node_id: "a",
    field: null,
    pre_existing: false,
    ...overrides,
  });

  it("shows only what this turn introduced and the user can act on in chat", () => {
    const draft = {
      issues: [
        issue({ code: "new_error" }),
        issue({ code: "old_error", pre_existing: true }),
        issue({ code: "needs_setup", severity: "setup" }),
        issue({ code: "new_warning", severity: "warning" }),
      ],
    } as BuilderDraft;

    expect(reportableIssues(draft).map((i) => i.code)).toEqual(["new_error", "new_warning"]);
  });
});

describe("changeKind", () => {
  it("groups operations for the badges", () => {
    const kind = (op: string) => changeKind({ op, summary: "", node_ids: [] } as never);
    expect(kind("add_node")).toBe("add");
    expect(kind("add_tool")).toBe("add");
    expect(kind("update_node")).toBe("update");
    expect(kind("connect")).toBe("update");
    expect(kind("remove_node")).toBe("remove");
    expect(kind("disconnect")).toBe("remove");
  });
});

describe("changesAffectLayout", () => {
  const change = (op: string) => ({ op, summary: "", node_ids: [] }) as never;

  it("is true when nodes or connections were added or removed", () => {
    for (const op of ["add_node", "add_tool", "remove_node", "connect", "disconnect"]) {
      expect(changesAffectLayout([change("update_node"), change(op)])).toBe(true);
    }
  });

  it("is false when only settings changed, so nothing the user arranged moves", () => {
    expect(changesAffectLayout([change("update_node"), change("update_node")])).toBe(false);
    expect(changesAffectLayout([])).toBe(false);
  });
});

describe("change preview marks", () => {
  it("marks added and changed nodes and clears the marks", () => {
    const nodes = [node("a"), node("b"), node("c")];
    const marked = markAiChanges(nodes, [
      { op: "add_node", summary: "Added b", node_ids: ["b"] },
      { op: "update_node", summary: "Updated c", node_ids: ["c"] },
    ]);
    expect(marked.map((n) => n.data.aiChange)).toEqual([undefined, "added", "changed"]);
    expect(clearAiChanges(marked).map((n) => n.data.aiChange)).toEqual([undefined, undefined, undefined]);
    expect(serializeCanvasForDraft(marked, []).nodes[1]).not.toHaveProperty("data.aiChange");
  });
});

describe("slash commands and mentions", () => {
  it("parses known commands only", () => {
    expect(parseSlashCommand("/explain the billing step")).toEqual({ command: "explain", rest: "the billing step" });
    expect(parseSlashCommand("/UNDO")).toEqual({ command: "undo", rest: "" });
    expect(parseSlashCommand("/dance now")).toBeNull();
    expect(parseSlashCommand("explain /review")).toBeNull();
  });

  it("resolves @Name mentions against the canvas, longest-safe", () => {
    const nodes = [node("1", { name: "Support Agent" }), node("2", { name: "Support" }), node("3", { name: "Reply (final)" })];
    expect(mentionedNodeIds("make @Support Agent shorter", nodes)).toEqual(["1", "2"]);
    expect(mentionedNodeIds("fix @Reply (final) please", nodes)).toEqual(["3"]);
    expect(mentionedNodeIds("no mentions here", nodes)).toEqual([]);
  });
});

describe("splitNodeMentions", () => {
  const nodes = [
    { id: "1", name: "Support Agent" },
    { id: "2", name: "Support" },
    { id: "3", name: "Search Documentation" },
  ];

  it("turns @Name and quoted names into chips, longest name first", () => {
    expect(splitNodeMentions('Fix "Search Documentation" and @Support Agent now', nodes)).toEqual([
      { text: "Fix " },
      { node: nodes[2] },
      { text: " and " },
      { node: nodes[0] },
      { text: " now" },
    ]);
  });

  it("accepts curly quotes and leaves unknown names as text", () => {
    expect(splitNodeMentions("the “Support” step and “Nothing”", nodes)).toEqual([
      { text: "the " },
      { node: nodes[1] },
      { text: " step and “Nothing”" },
    ]);
    expect(splitNodeMentions("plain text", nodes)).toEqual([{ text: "plain text" }]);
  });
});


describe("splitNodeMentions with steps that share a name", () => {
  const nodes = [
    { id: "tool-1", name: "Exchange Rates", type: "toolBuilderNode" },
    { id: "api-1", name: "Exchange Rates", type: "apiToolNode" },
  ];

  it("resolves the mention to the step the person picked", () => {
    const segments = splitNodeMentions("Explain @Exchange Rates please", nodes, ["api-1"]);
    const chip = segments.find((s) => "node" in s) as { node: { id: string } };
    expect(chip.node.id).toBe("api-1");
  });

  it("keeps the first match when nothing was picked", () => {
    const segments = splitNodeMentions("Explain @Exchange Rates please", nodes);
    const chip = segments.find((s) => "node" in s) as { node: { id: string } };
    expect(chip.node.id).toBe("tool-1");
  });
});

describe("splitNodeMentions when both namesakes were tagged", () => {
  it("takes the one picked first", () => {
    const nodes = [
      { id: "tool-1", name: "Expense Policy", type: "toolBuilderNode" },
      { id: "kb-1", name: "Expense Policy", type: "knowledgeBaseNode" },
    ];
    const segments = splitNodeMentions("Check @Expense Policy", nodes, ["kb-1", "tool-1"]);
    const chip = segments.find((s) => "node" in s) as { node: { id: string } };
    expect(chip.node.id).toBe("kb-1");
  });
});
