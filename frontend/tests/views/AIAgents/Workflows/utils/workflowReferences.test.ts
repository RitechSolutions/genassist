import { describe, it, expect } from "vitest";
import { Node } from "reactflow";
import {
  REFERENCE_FIELDS,
  ReferenceTarget,
  acceptedTargets,
  findMissingReferences,
  getReferencedKinds,
  replaceReferences,
} from "@/views/AIAgents/Workflows/utils/workflowReferences";

const node = (id: string, type: string, data: Record<string, unknown>): Node => ({
  id,
  type,
  position: { x: 0, y: 0 },
  data,
});

const target = (id: string, extra: Partial<ReferenceTarget> = {}): ReferenceTarget => ({
  id,
  name: `Name ${id}`,
  label: `Label ${id}`,
  isActive: true,
  ...extra,
});

const field = (type: string, key: string) =>
  REFERENCE_FIELDS[type].find((f) => f.key === key)!;

describe("getReferencedKinds", () => {
  it("lists the kinds with at least one id set", () => {
    const nodes = [
      node("a", "agentNode", { providerId: "p1", fallbackChainId: "" }),
      node("k", "knowledgeBaseNode", { selectedBases: [] }),
      node("s", "slackMessageNode", { app_settings_id: "s1" }),
      node("t", "templateNode", { template: "hi" }),
    ];
    expect(getReferencedKinds(nodes).sort()).toEqual(["appSetting", "llmProvider"]);
  });
});

describe("findMissingReferences", () => {
  it("groups every place that uses the same unknown id", () => {
    const nodes = [
      node("a", "agentNode", { name: "Support", providerId: "old", compactingModel: "old" }),
      node("r", "routerNode", { name: "Route", providerId: "old" }),
      node("m", "llmModelNode", { name: "Summary", providerId: "here" }),
    ];
    const missing = findMissingReferences(nodes, { llmProvider: new Set(["here"]) });
    expect(missing).toHaveLength(1);
    expect(missing[0]).toMatchObject({ kind: "llmProvider", ids: ["old"], multiple: false });
    expect(missing[0].places.map((p) => [p.nodeName, p.field.key])).toEqual([
      ["Support", "providerId"],
      ["Support", "compactingModel"],
      ["Route", "providerId"],
    ]);
  });

  it("keeps different unknown ids apart and orders them by kind", () => {
    const nodes = [
      node("s", "slackMessageNode", { app_settings_id: "s-old" }),
      node("a", "agentNode", { providerId: "p-old" }),
      node("b", "agentNode", { providerId: "p-other" }),
    ];
    const missing = findMissingReferences(nodes, {
      llmProvider: new Set(),
      appSetting: new Set(),
    });
    expect(missing.map((m) => `${m.kind}:${m.ids}`)).toEqual([
      "llmProvider:p-old",
      "llmProvider:p-other",
      "appSetting:s-old",
    ]);
  });

  it("gives a list field one entry for all the ids it misses", () => {
    const nodes = [
      node("k", "knowledgeBaseNode", { selectedBases: ["kb1", "gone", "gone", "lost"] }),
    ];
    const missing = findMissingReferences(nodes, { knowledgeBase: new Set(["kb1"]) });
    expect(missing).toHaveLength(1);
    expect(missing[0]).toMatchObject({ ids: ["gone", "lost"], multiple: true });
    expect(missing[0].places).toHaveLength(1);
  });

  it("groups list fields only when they miss the same ids", () => {
    const nodes = [
      node("en", "knowledgeBaseNode", { name: "English", selectedBases: ["a", "shared"] }),
      node("fr", "knowledgeBaseNode", { name: "French", selectedBases: ["b", "shared"] }),
      node("copy", "knowledgeBaseNode", { name: "Copy", selectedBases: ["shared", "a"] }),
    ];
    const missing = findMissingReferences(nodes, { knowledgeBase: new Set() });
    expect(missing.map((m) => m.places.map((p) => p.nodeName))).toEqual([
      ["English", "Copy"],
      ["French"],
    ]);
  });

  it("skips kinds it couldn't list, empty values and variables", () => {
    const nodes = [
      node("a", "agentNode", { providerId: "old" }),
      node("w", "createWorkflowScheduleNode", { agentId: "{{source.agent}}" }),
      node("j", "jiraNode", { app_settings_id: "" }),
    ];
    expect(findMissingReferences(nodes, { agent: new Set(), appSetting: new Set() })).toEqual([]);
  });

  it("uses the name a node keeps for its target", () => {
    const nodes = [
      node("w", "workflowExecutorNode", { workflowId: "old", workflowName: "Billing flow" }),
    ];
    expect(findMissingReferences(nodes, { workflow: new Set() })[0].name).toBe("Billing flow");
  });
});

describe("acceptedTargets", () => {
  it("offers only what every field's own picker would", () => {
    const targets = [
      target("tts", { type: "tts" }),
      target("stt", { type: "stt" }),
      target("both", { type: "both" }),
    ];
    const tts = field("ttsNode", "audioProviderId");
    const stt = field("sttNode", "audioProviderId");
    expect(acceptedTargets(targets, [tts]).map((t) => t.id)).toEqual(["tts", "both"]);
    expect(acceptedTargets(targets, [tts, stt]).map((t) => t.id)).toEqual(["both"]);
  });

  it("matches configuration vars by type and leaves out inactive ones", () => {
    const targets = [
      target("slack", { type: "Slack" }),
      target("off", { type: "Slack", isActive: false }),
      target("jira", { type: "Jira" }),
    ];
    const slack = field("slackMessageNode", "app_settings_id");
    expect(acceptedTargets(targets, [slack]).map((t) => t.id)).toEqual(["slack"]);
  });
});

describe("replaceReferences", () => {
  it("replaces a single id and leaves other nodes untouched", () => {
    const other = node("r", "routerNode", { providerId: "old" });
    const nodes = [node("a", "agentNode", { providerId: "old", memory: true }), other];
    const result = replaceReferences(nodes, [
      { nodeId: "a", field: field("agentNode", "providerId"), from: ["old"], to: [target("new")] },
    ]);
    expect(result[0].data).toEqual({ providerId: "new", memory: true });
    expect(result[1]).toBe(other);
    expect(nodes[0].data.providerId).toBe("old");
  });

  it("swaps a list's missing ids for the picked ones and keeps the rest", () => {
    const nodes = [node("k", "knowledgeBaseNode", { selectedBases: ["kb1", "old1", "old2"] })];
    const result = replaceReferences(nodes, [
      {
        nodeId: "k",
        field: field("knowledgeBaseNode", "selectedBases"),
        from: ["old1", "old2"],
        to: [target("kb1"), target("kb2")],
      },
    ]);
    expect(result[0].data.selectedBases).toEqual(["kb1", "kb2"]);
  });

  it("updates the name a node keeps alongside the id", () => {
    const nodes = [node("w", "workflowExecutorNode", { workflowId: "old", workflowName: "Old" })];
    const result = replaceReferences(nodes, [
      {
        nodeId: "w",
        field: field("workflowExecutorNode", "workflowId"),
        from: ["old"],
        to: [target("new", { name: "New flow" })],
      },
    ]);
    expect(result[0].data).toEqual({ workflowId: "new", workflowName: "New flow" });
  });

  it("keeps only the new workflow's inputs, as the executor's picker does", () => {
    const nodes = [
      node("w", "workflowExecutorNode", {
        workflowId: "old",
        inputParameters: { topic: "{{input.topic}}", stale: "x" },
      }),
    ];
    const result = replaceReferences(nodes, [
      {
        nodeId: "w",
        field: field("workflowExecutorNode", "workflowId"),
        from: ["old"],
        to: [target("new", { inputs: ["topic", "language"] })],
      },
    ]);
    expect(result[0].data.inputParameters).toEqual({ topic: "{{input.topic}}", language: "" });
  });

  it("leaves an executor's inputs alone when the new workflow declares none", () => {
    const nodes = [
      node("w", "workflowExecutorNode", { workflowId: "old", inputParameters: { topic: "x" } }),
    ];
    const result = replaceReferences(nodes, [
      {
        nodeId: "w",
        field: field("workflowExecutorNode", "workflowId"),
        from: ["old"],
        to: [target("new")],
      },
    ]);
    expect(result[0].data.inputParameters).toEqual({ topic: "x" });
  });

  it("fits an ML model's inputs to the new model, as its picker does", () => {
    const nodes = [
      node("m", "mlModelInferenceNode", {
        modelId: "old",
        modelName: "Churn",
        inferenceInputs: { age: "{{input.age}}", income: "1", tenure: null },
      }),
    ];
    const result = replaceReferences(nodes, [
      {
        nodeId: "m",
        field: field("mlModelInferenceNode", "modelId"),
        from: ["old"],
        to: [target("new", { name: "Churn v2", inputs: ["age", "tenure"] })],
      },
    ]);
    expect(result[0].data).toEqual({
      modelId: "new",
      modelName: "Churn v2",
      inferenceInputs: { age: "{{input.age}}", tenure: "" },
    });
  });
});
